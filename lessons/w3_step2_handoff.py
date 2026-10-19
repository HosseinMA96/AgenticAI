"""Week 3, Step 2 (lesson): handoff, where the model picks the path (book Ch 7, D36).

A "quick" agent (no reasoning) gets every question. If it needs math or judgement, it calls
handoff_to_deep, a tool MAF injects, and a "deep" agent (reasoning on) takes over the conversation.
Same split as our Router (D31), but the model decides instead of our code.

Run: uv run python lessons/w3_step2_handoff.py
"""

import asyncio
import json

from agent_framework import Agent
from agent_framework.orchestrations import HandoffBuilder

from finsight.config import ANALYSIS_REASONING, PAGE_FORMAT, SEARCH_MODE
from finsight.dataset import SPLITS
from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.tools.calculator import calculator
from finsight.tools.search_filings import make_search_filings

# Two the Router labelled lookup, two it labelled analysis (router eval, D33).
IDS = ["financebench_id_01148", "financebench_id_02024", "financebench_id_03856", "financebench_id_00585"]


def build():
    tools = [make_search_filings(SEARCH_MODE, PAGE_FORMAT), calculator]
    quick = Agent(
        client=get_client(), name="quick",
        # The handoff tool's description comes from the target's description, so this line steers the choice.
        description="Answers questions that need a calculation, a comparison or a judgement.",
        instructions="You answer questions about one 10-K filing, in two sentences, citing pages. "
        "Answer yourself only if the filing states the answer directly. If it needs a calculation, "
        "a comparison or a judgement, hand off to the deep agent instead of answering.",
        tools=tools, default_options=AGENT_DEFAULTS,
        # Required by HandoffBuilder (MAF 1.20): history is saved after every model call, so a handoff
        # that cuts a tool loop short leaves the conversation consistent for the next agent.
        require_per_service_call_history_persistence=True,
    )
    deep = Agent(
        client=get_client(), name="deep",
        description="Careful analyst for calculations, comparisons and judgements.",
        instructions="You answer questions about one 10-K filing, in two sentences, citing pages. "
        "Search the filing, check the numbers with the calculator, then answer.",
        tools=tools, default_options=AGENT_DEFAULTS | {"reasoning": {"effort": ANALYSIS_REASONING}},
        require_per_service_call_history_persistence=True,
    )
    # One way only: quick → deep. deep can't hand back, so they can't ping-pong.
    return HandoffBuilder(participants=[quick, deep]).with_start_agent(quick).add_handoff(quick, [deep]).build()


async def main() -> None:
    rows = {r["id"]: r for r in map(json.loads, (SPLITS / "dev.jsonl").open())}
    for qid in IDS:
        row = rows[qid]
        # A fresh workflow per question: the handoff conversation is shared state.
        result = await build().run(f"Filing: {row['doc_name']}\n\nQuestion: {row['question']}")
        print(f"\n=== {qid}: {row['question'][:80]}")
        for out in result.get_outputs():  # one AgentResponse per agent turn, in order
            calls = [c.name for m in out.messages for c in m.contents if c.type == "function_call"]
            print(f"  [{out.messages[-1].author_name or '?'}] tools={calls}")
            if out.text:
                print(f"     {out.text[:200]!r}")
        print(f"  gold: {row['answer'][:120]!r}")


asyncio.run(main())
