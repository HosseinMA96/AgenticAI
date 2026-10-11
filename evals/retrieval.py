"""Retrieval eval: does search put the gold evidence pages in the top k? (D21)

    uv run python -m evals.retrieval --index page [--split dev] [--limit N]

No agent and no answer: only search results scored against FinanceBench's gold pages.
Writes evals/results/<timestamp>_retrieval-<index>.json and appends rows to evals/retrieval.md.
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from evals.scorers import hit_at_k, recall_at_k
from finsight.dataset import SPLITS
from finsight.rag.ingest import index_name
from finsight.rag.search import MODES, embed_query, search

EVALS = Path(__file__).parent
KS = (1, 3, 5)


async def run_question(index: str, row: dict) -> dict:
    # The raw FinanceBench question is the query. In the real app the agent writes
    # its own query, so this measures the index, not the agent's search skill.
    vector = await embed_query(row["question"])  # once per question, shared by all modes
    out = {"id": row["id"], "gold_pages": row["evidence_pages"], "modes": {}}
    for mode in MODES:
        docs = await search(index, row["question"], row["doc_name"], mode, top=max(KS), vector=vector)
        # Headline: each chunk scored by its main page (D22). For page chunks
        # that's simply its page. "any" also credits every page a chunk touches.
        retrieved = [[d["main_page"]] for d in docs]
        any_page = [d["pages"] for d in docs]
        out["modes"][mode] = {
            "retrieved": any_page,
            **{f"hit@{k}": hit_at_k(retrieved, row["evidence_pages"], k) for k in KS},
            **{f"recall@{k}": recall_at_k(retrieved, row["evidence_pages"], k) for k in KS},
            "recall@5 any-page": recall_at_k(any_page, row["evidence_pages"], 5),
        }
    return out


async def main(chunker: str, split: str, limit: int | None) -> None:
    rows = [json.loads(line) for line in (SPLITS / f"{split}.jsonl").open()][:limit]
    index = index_name(chunker)
    results = []
    for row in rows:  # sequential: 42 questions take about a minute, no rate-limit worries
        results.append(await run_question(index, row))

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    metrics = [f"{m}@{k}" for m in ("hit", "recall") for k in KS] + ["recall@5 any-page"]
    summary = {
        mode: {m: sum(r["modes"][mode][m] for r in results) / len(results) for m in metrics}
        for mode in MODES
    }
    path = EVALS / "results" / f"{stamp}_retrieval-{chunker}.json"
    path.write_text(json.dumps({"index": index, "split": split, "n": len(results), "summary": summary, "rows": results}, indent=1))

    table = EVALS / "retrieval.md"
    if not table.exists():
        table.write_text(
            "# Retrieval leaderboard\n\nOne row per (run, search mode). Queries are the raw questions. Scored by main page; any-page shown for comparison (D21, D22).\n\n"
            "| when | index | mode | split | n | " + " | ".join(metrics) + " |\n"
            "|---|---|---|---|---|" + "---|" * len(metrics) + "\n"
        )
    with table.open("a") as f:
        for mode, s in summary.items():
            cells = " | ".join(f"{s[m]:.0%}" for m in metrics)
            line = f"| {stamp} | {index} | {mode} | {split} | {len(results)} | {cells} |"
            f.write(line + "\n")
            print(line)
    print(f"wrote {path.name}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--index", choices=["page", "fixed"], required=True)
    p.add_argument("--split", default="dev")
    p.add_argument("--limit", type=int)
    a = p.parse_args()
    asyncio.run(main(a.index, a.split, a.limit))
