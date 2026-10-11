"""Eval harness v0 (book Ch 10, D14).

    uv run python -m evals.run --split dev [--limit N] [--config NAME]

Runs the analyst on each question, scores it, writes evals/results/<timestamp>_<config>.json
and appends one row to evals/leaderboard.md.
"""

import argparse
import asyncio
import json
import random
import statistics
import time
from datetime import datetime
from pathlib import Path

import openai
from agent_framework import Agent

from evals.judge import judge_answer, judge_citation
from evals.scorers import citation_hit, numbers_match, parse_number
from finsight.agents.analyst import ask, build_analyst, edgar_stdio
from finsight.config import CHEAP_MODEL, MAIN_MODEL
from finsight.dataset import SPLITS
from finsight.limits import count_tool_calls, limit_hit
from finsight.pricing import cost_usd
from finsight.tools.filings import load_pages

EVALS = Path(__file__).parent
CONCURRENCY = 3  # questions in flight at once; 4 hit gpt-5.4's tokens-per-minute quota (429)
MAX_RETRIES = 6


def _is_rate_limit(e: BaseException) -> bool:
    # MAF wraps the OpenAI error, so look at the cause too.
    return isinstance(e, openai.RateLimitError) or isinstance(e.__cause__, openai.RateLimitError)


async def with_retry(make_call):
    """Wait and retry on 429. A rate limit is the quota talking, not a wrong answer,
    so it must never be scored as one."""
    for attempt in range(MAX_RETRIES):
        try:
            return await make_call()
        except Exception as e:
            if not _is_rate_limit(e) or attempt == MAX_RETRIES - 1:
                raise
            delay = min(60, 2 ** attempt * 5) * (0.5 + random.random())  # backoff with jitter
            print(f"   ⏳ rate limited, retrying in {delay:.0f}s")
            await asyncio.sleep(delay)


async def score_one(agent: Agent, row: dict) -> dict:
    start = time.monotonic()
    out = {"id": row["id"], "company": row["company"], "answer_type": row["answer_type"], "gold": row["answer"]}
    try:
        response = await with_retry(lambda: ask(agent, row["doc_name"], row["question"]))
        answer = response.value
    except Exception as e:  # a crash is a wrong answer, not a dead eval run
        return out | {"error": repr(e), "correct": False, "citation_hit": False, "citation_supported": False,
                      "latency_s": time.monotonic() - start, "tool_calls": 0, "cost_usd": 0.0, "usage": {}}
    usage = response.usage_details or {}
    out |= {
        "latency_s": time.monotonic() - start,
        "tool_calls": count_tool_calls(response),
        "limit_hit": limit_hit(response),
        "usage": usage,
        "cost_usd": cost_usd(MAIN_MODEL, usage),
        "found": answer.found,
        "answer": answer.answer,
        "value": answer.value,
        "citations": answer.citations,
        "gold_pages": row["evidence_pages"],
    }
    judge_cost = 0.0

    # Correctness: numbers in code, written answers by the judge (D14).
    if row["answer_type"] == "numeric":
        out["correct"] = numbers_match(parse_number(row["answer"]), answer.value)
    else:
        verdict, u = await with_retry(lambda: judge_answer(row["question"], row["answer"], answer.answer))
        out |= {"correct": verdict.correct, "judge_reason": verdict.reason}
        judge_cost += cost_usd(MAIN_MODEL, u)

    # Citations: free strict check first; the cheap judge only on a miss (D14, user's idea).
    out["citation_hit"] = citation_hit(answer.citations, row["evidence_pages"])
    out["citation_supported"] = out["citation_hit"]
    if not out["citation_hit"] and answer.found and answer.citations:
        pages = load_pages(row["doc_name"])
        cited = {n: pages[n - 1] for n in answer.citations if 1 <= n <= len(pages)}
        verdict, u = await with_retry(lambda: judge_citation(answer.answer, cited))
        out |= {"citation_supported": verdict.correct, "citation_reason": verdict.reason}
        judge_cost += cost_usd(CHEAP_MODEL, u)

    out["judge_cost_usd"] = judge_cost
    return out


def _rate(rows: list[dict]) -> float | None:
    return sum(r["correct"] for r in rows) / len(rows) if rows else None


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0%}"


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    lat = sorted(r["latency_s"] for r in rows)
    tok = lambda key: sum((r["usage"] or {}).get(key) or 0 for r in rows)
    by_type = {t: [r for r in rows if r["answer_type"] == t] for t in ("numeric", "text")}
    return {
        "n": n,
        "accuracy": sum(r["correct"] for r in rows) / n,
        # None, not 0%, when a run has no questions of that type (e.g. a small --limit).
        "accuracy_numeric": _rate(by_type["numeric"]),
        "accuracy_text": _rate(by_type["text"]),
        "citation_hit": sum(r["citation_hit"] for r in rows) / n,
        "citation_supported": sum(r["citation_supported"] for r in rows) / n,
        "tokens_in": tok("input_token_count"),
        "tokens_cached": tok("cache_read_input_token_count"),
        "tokens_out": tok("output_token_count"),
        "cost_usd": sum(r["cost_usd"] for r in rows),
        "judge_cost_usd": sum(r.get("judge_cost_usd", 0) for r in rows),
        "latency_p50_s": statistics.median(lat),
        "latency_p95_s": lat[min(n - 1, round(0.95 * (n - 1)))],
        "tool_calls_avg": sum(r["tool_calls"] for r in rows) / n,
        "errors": sum("error" in r for r in rows),
        "limit_hits": sum(r.get("limit_hit", False) for r in rows),
    }


async def main(split: str, limit: int | None, config: str) -> None:
    if split != "dev":
        # CLAUDE.md: test runs only at the end of week 5, with the user's explicit OK each time.
        if input(f"Run the held-out '{split}' split? Type yes: ") != "yes":
            return
    rows = [json.loads(l) for l in (SPLITS / f"{split}.jsonl").read_text().splitlines()][:limit]
    sem = asyncio.Semaphore(CONCURRENCY)
    async with edgar_stdio() as edgar:
        agent = build_analyst(edgar)

        async def bounded(row: dict) -> dict:
            async with sem:
                r = await score_one(agent, row)
                print(f"{'✅' if r['correct'] else '❌'} {r['id']} {r['company']:16s} cite={'✓' if r['citation_supported'] else '✗'}")
                return r

        results = await asyncio.gather(*(bounded(r) for r in rows))

    summary = summarize(results)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (EVALS / "results").mkdir(exist_ok=True)
    out_file = EVALS / "results" / f"{stamp}_{config}.json"
    out_file.write_text(json.dumps({"config": config, "split": split, "summary": summary, "rows": results}, indent=1))

    board = EVALS / "leaderboard.md"
    if not board.exists():
        board.write_text(
            "# Leaderboard\n\nOne row per eval run (CLAUDE.md). Cost is the agent only; judge cost is separate.\n\n"
            "| when | config | split | n | accuracy | numeric | text | citation hit | citation supported "
            "| tokens in / cached / out | $ agent | $ judge | p50 s | p95 s | tool calls avg |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        )
    s = summary
    with board.open("a") as f:
        f.write(
            f"| {stamp} | {config} | {split} | {s['n']} | {s['accuracy']:.0%} | {_pct(s['accuracy_numeric'])} "
            f"| {_pct(s['accuracy_text'])} | {s['citation_hit']:.0%} | {s['citation_supported']:.0%} "
            f"| {s['tokens_in']:,} / {s['tokens_cached']:,} / {s['tokens_out']:,} | {s['cost_usd']:.2f} "
            f"| {s['judge_cost_usd']:.2f} | {s['latency_p50_s']:.0f} | {s['latency_p95_s']:.0f} | {s['tool_calls_avg']:.1f} |\n"
        )
    print(json.dumps(summary, indent=1))
    print(f"\nsaved {out_file.relative_to(EVALS.parent)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="dev")
    p.add_argument("--limit", type=int)
    p.add_argument("--config", default="baseline")
    a = p.parse_args()
    asyncio.run(main(a.split, a.limit, a.config))
