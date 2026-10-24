"""Eval harness v0 (book Ch 10, D14).

    uv run python -m evals.run --split dev [--limit N] [--config NAME] [--workflow [--no-edgar]]

Runs the analyst (or, with --workflow, the week-3 workflow graph) on each question, scores it, writes evals/results/<timestamp>_<config>.json
and appends one row to evals/leaderboard.md.
"""

import argparse
import asyncio
import json
import random
import statistics
from collections import Counter
import time
from datetime import datetime
from pathlib import Path

import openai
from agent_framework import Agent

from evals.judge import judge_answer, judge_citation
from evals.scorers import citation_hit, numbers_match, parse_number
from finsight.agents.analyst import ask, build_analyst, edgar_stdio
from finsight.config import CHEAP_MODEL, MAIN_MODEL, PAGE_FORMAT, SEARCH_MODE
from finsight.dataset import SPLITS
from finsight.evidence import unread_citations
from finsight.limits import count_tool_calls, limit_hit
from finsight.memory.episodes import InMemoryEpisodeStore
from finsight.orchestration.messages import Question
from finsight.orchestration.workflow import build_workflow
from finsight.pricing import cost_usd
from finsight.rag.search import MODES
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


async def run_agent(agent: Agent, row: dict):
    """One question through the single analyst. Returns (Answer, metrics)."""
    response = await with_retry(lambda: ask(agent, row["doc_name"], row["question"]))
    usage = response.usage_details or {}
    return response.value, {
        "tool_calls": count_tool_calls(response),
        # Which tools, in order: shows MCP vs local use, and later feeds trajectory metrics (week 5).
        "tools_used": [c.name for m in response.messages for c in m.contents if c.type == "function_call"],
        "limit_hit": limit_hit(response),
        "unread_citations": unread_citations(response.value.citations, response),  # D30: cited but never read
        "usage": usage,
        "cost_usd": cost_usd(MAIN_MODEL, usage),
    }


async def run_workflow(tools: list, row: dict, research: str = "router"):
    """One question through the workflow graph. Returns (Answer or None if oos, metrics).
    A fresh workflow per question (and per 429 retry): one workflow object runs one question at a time."""
    q = Question(doc_name=row["doc_name"], question=row["question"])
    result = await with_retry(lambda: build_workflow(*tools, research=research).run(q))
    if requests := result.get_request_info_events():
        # D35: no human in an eval. Score what the human would have seen; don't resume with a made-up decision.
        c = requests[0].data.checked
        status, answer, route, verdict, attempts, steps = "needs_human", c.draft.answer, c.draft.routed.route, c.verdict, c.draft.attempt, c.steps
    else:
        r = result.get_outputs()[-1]
        status, answer, route, verdict, attempts, steps = r.status, r.answer, r.route, r.verdict, r.attempts, r.steps
    research_steps = [st for st in steps if st.agent == "research"]
    usage: dict = {}
    for st in steps:  # one usage dict for the whole question, so the leaderboard columns stay comparable
        for k, v in st.usage.items():
            if isinstance(v, int):
                usage[k] = usage.get(k, 0) + v
    cost_by_agent: dict = {}
    for st in steps:
        cost_by_agent[st.agent] = cost_by_agent.get(st.agent, 0.0) + cost_usd(st.model, st.usage)
    return answer, {
        "tool_calls": sum(len(st.tools_used) for st in research_steps),
        "tools_used": [t for st in research_steps for t in st.tools_used],
        "limit_hit": any(st.limit_hit for st in research_steps),
        "unread_citations": research_steps[-1].unread_citations if research_steps else [],
        "usage": usage,
        "cost_usd": sum(cost_by_agent.values()),
        "cost_by_agent": cost_by_agent,
        "route": route.label,
        "handled_by": [st.detail for st in research_steps if st.detail],  # handoff: "quick" or "quick→deep"
        "status": status,
        "attempts": attempts,
        "verified": bool(verdict and verdict.supported),
        "verifier_problem": verdict.problem if verdict else None,
    }


async def score_one(run, row: dict) -> dict:
    """run: run_agent or run_workflow with its first argument bound."""
    start = time.monotonic()
    out = {"id": row["id"], "company": row["company"], "answer_type": row["answer_type"], "gold": row["answer"]}
    try:
        answer, metrics = await run(row)
    except Exception as e:  # a crash is a wrong answer, not a dead eval run
        return out | {"error": repr(e), "correct": False, "citation_hit": False, "citation_supported": False,
                      "latency_s": time.monotonic() - start, "tool_calls": 0, "cost_usd": 0.0, "usage": {}}
    out |= {"latency_s": time.monotonic() - start, **metrics, "judge_cost_usd": 0.0}
    if answer is None:  # the Router said oos: no answer, so it's wrong (every dev question is in scope)
        return out | {"correct": False, "citation_hit": False, "citation_supported": False}
    out |= {
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


def summarize_workflow(rows: list[dict]) -> dict:
    """Extra numbers only the workflow has: per Router label, retries, human hand-offs, $ per agent."""
    ok = [r for r in rows if "status" in r]
    labels = {lab: [r for r in ok if r["route"] == lab] for lab in ("lookup", "analysis", "oos")}
    human = [r for r in ok if r["status"] == "needs_human"]
    retried = [r for r in ok if r["attempts"] == 2]
    agents = {a for r in ok for a in r["cost_by_agent"]}
    return {
        "by_label": {lab: {"n": len(rs), "accuracy": _rate(rs)} for lab, rs in labels.items()},
        "status": {st: sum(r["status"] == st for r in ok) for st in {r["status"] for r in ok}},
        "retried": len(retried),
        "retried_then_verified": sum(r["status"] == "verified" for r in retried),
        # D35: were the Verifier's final rejections right? Gold says whether those answers were wrong.
        "needs_human": len(human),
        "needs_human_but_correct": sum(r["correct"] for r in human),
        "verified_but_wrong": sum(r["status"] == "verified" and not r["correct"] for r in ok),
        "cost_by_agent": {a: sum(r["cost_by_agent"].get(a, 0.0) for r in ok) for a in sorted(agents)},
        # Handoff only: who answered the first attempt, and how that lines up with the Router's label.
        "handled_by_vs_route": dict(Counter(f"{r['route']}:{r['handled_by'][0]}" for r in ok if r.get("handled_by"))),
    }


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


async def main(split: str, limit: int | None, config: str, prompt: str, search_mode: str, page_format: str, memory: bool,
               workflow: bool = False, edgar: bool = True, research: str = "router") -> None:
    if split != "dev":
        # CLAUDE.md: test runs only at the end of week 5, with the user's explicit OK each time.
        if input(f"Run the held-out '{split}' split? Type yes: ") != "yes":
            return
    rows = [json.loads(l) for l in (SPLITS / f"{split}.jsonl").read_text().splitlines()][:limit]
    sem = asyncio.Semaphore(CONCURRENCY)
    async with edgar_stdio() as edgar_tool:
        if workflow:
            # The workflow uses the config defaults for prompt, search and pages; only edgar can be switched off.
            run = lambda row: run_workflow([edgar_tool] if edgar else [], row, research)
        else:
            # A fresh store per run: never the saved episodes file, so every eval starts empty (D29).
            store = InMemoryEpisodeStore() if memory else None
            agent = build_analyst(edgar_tool, prompt=prompt, search_mode=search_mode, page_format=page_format, memory=store)
            run = lambda row: run_agent(agent, row)

        async def bounded(row: dict) -> dict:
            async with sem:
                r = await score_one(run, row)
                print(f"{'✅' if r['correct'] else '❌'} {r['id']} {r['company']:16s} cite={'✓' if r['citation_supported'] else '✗'}")
                return r

        results = await asyncio.gather(*(bounded(r) for r in rows))

    summary = summarize(results)
    if workflow:
        summary["workflow"] = summarize_workflow(results)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (EVALS / "results").mkdir(exist_ok=True)
    out_file = EVALS / "results" / f"{stamp}_{config}.json"
    out_file.write_text(json.dumps({"config": config, "workflow": workflow, "edgar": edgar, "research": research, "prompt": prompt, "search_mode": search_mode, "page_format": page_format, "memory": memory, "split": split, "summary": summary, "rows": results}, indent=1))

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
    p.add_argument("--prompt", default="analyst", help="system prompt file in src/finsight/prompts/, without .md")
    p.add_argument("--search-mode", default=SEARCH_MODE, choices=MODES, help="search_filings mode (D25)")
    p.add_argument("--page-format", default=PAGE_FORMAT, choices=["text", "image"], help="pages as text or images (D26)")
    p.add_argument("--memory", action="store_true", help="episodic memory, starting from an empty store (D29)")
    p.add_argument("--workflow", action="store_true", help="run the week-3 workflow graph instead of the single analyst")
    p.add_argument("--no-edgar", action="store_true", help="with --workflow: leave the edgar MCP tool out of Research")
    p.add_argument("--research", default="router", choices=["router", "handoff", "makerchecker", "concurrent"], help="with --workflow: Research variant (D36)")
    a = p.parse_args()
    asyncio.run(main(a.split, a.limit, a.config, a.prompt, a.search_mode, a.page_format, a.memory, a.workflow, not a.no_edgar, a.research))
