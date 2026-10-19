"""Router eval: does it catch a question asked against the wrong company's filing? (D31, D33)

    uv run python -m evals.router [--split dev] [--limit N]

Each question runs twice: with its real filing (should NOT be oos) and with a filing from
a different company (should be oos). Writes evals/results/<timestamp>_router.json.
"""

import argparse
import asyncio
import json
import random
from collections import Counter
from datetime import datetime
from pathlib import Path

from finsight.agents.router import build_router, route
from finsight.config import CHEAP_MODEL
from finsight.dataset import SPLITS
from finsight.pricing import cost_usd

EVALS = Path(__file__).parent


async def main(split: str, limit: int | None) -> None:
    rows = [json.loads(line) for line in (SPLITS / f"{split}.jsonl").open()][:limit]
    all_rows = [json.loads(line) for line in (SPLITS / f"{split}.jsonl").open()]
    rng = random.Random(0)  # fixed seed: the same wrong filings every run (D33)
    router = build_router()

    results = []
    for row in rows:
        wrong = rng.choice([r["doc_name"] for r in all_rows if r["company"] != row["company"]])
        for doc, should_be_oos in ((row["doc_name"], False), (wrong, True)):
            response = await route(router, doc, row["question"])
            label = response.value.label
            results.append({
                "id": row["id"], "doc_name": doc, "should_be_oos": should_be_oos, "label": label,
                "correct": (label == "oos") == should_be_oos, "reason": response.value.reason,
                "cost_usd": cost_usd(CHEAP_MODEL, response.usage_details or {}),
            })

    real = [r for r in results if not r["should_be_oos"]]
    wrong = [r for r in results if r["should_be_oos"]]
    summary = {
        "caught_wrong_filing": sum(r["correct"] for r in wrong) / len(wrong),
        "wrongly_blocked": sum(not r["correct"] for r in real) / len(real),
        "in_scope_labels": dict(Counter(r["label"] for r in real)),
        "cost_usd": sum(r["cost_usd"] for r in results),
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = EVALS / "results" / f"{stamp}_router.json"
    path.write_text(json.dumps({"split": split, "n": len(rows), "summary": summary, "rows": results}, indent=1))
    print(json.dumps(summary, indent=1))
    for r in results:
        if not r["correct"]:
            print(f"✗ {r['id']} vs {r['doc_name']}: {r['label']} — {r['reason']}")
    print(f"→ {path.relative_to(EVALS.parent)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="dev")
    p.add_argument("--limit", type=int)
    a = p.parse_args()
    asyncio.run(main(a.split, a.limit))
