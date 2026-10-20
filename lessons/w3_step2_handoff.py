"""Week 3, Step 2 (lesson): handoff, where the model picks the path (book Ch 7, D36).

A "quick" agent (no reasoning) gets every question. If it needs math or judgement, it calls
handoff_to_deep, a tool MAF injects, and a "deep" agent (reasoning on) takes over the conversation.
Same split as our Router (D31), but the model decides instead of our code.

Run: uv run python lessons/w3_step2_handoff.py [--break]

--break: handoff both ways, with jobs that contradict each other (quick: "numbers go to deep";
deep: "searching goes to quick"). A question that needs both bounces back and forth. A safety cap
stops it at MAX_HANDOFFS, because nothing in the pattern itself does.
"""

import asyncio
import json
import sys

from agent_framework import Agent
from agent_framework.orchestrations import HandoffBuilder

from finsight.config import ANALYSIS_REASONING, PAGE_FORMAT, SEARCH_MODE
from finsight.dataset import SPLITS
from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.tools.calculator import calculator
from finsight.tools.search_filings import make_search_filings

# Two the Router labelled lookup, two it labelled analysis (router eval, D33).
IDS = ["financebench_id_01148", "financebench_id_02024", "financebench_id_03856", "financebench_id_00585"]
BREAK = "--break" in sys.argv
MAX_HANDOFFS = 6  # the safety cap for --break


def handoffs(conversation) -> int:
    return sum(c.type == "function_call" and c.name.startswith("handoff_to_") for m in conversation for c in m.contents)


# Normal jobs: quick answers what's stated, and hands off the rest.
QUICK = ("You answer questions about one 10-K filing, in two sentences, citing pages. "
         "Answer yourself only if the filing states the answer directly. If it needs a calculation, "
         "a comparison or a judgement, hand off to the deep agent instead of answering.")
DEEP = ("You answer questions about one 10-K filing, in two sentences, citing pages. "
        "Search the filing, check the numbers with the calculator, then answer.")
# Broken jobs: each one says the other does half the work, so a question needing both bounces.
QUICK_BROKEN = ("You find information in a 10-K filing. You never do arithmetic: if a question involves "
                "any numbers or calculation, hand off to the deep agent right away.")
DEEP_BROKEN = ("You do arithmetic only. You never search filings: if you don't already have the figures "
               "in the conversation, hand off to the quick agent to find them.")


def build():
    tools = [make_search_filings(SEARCH_MODE, PAGE_FORMAT), calculator]
    quick = Agent(
        client=get_client(), name="quick",
        # The handoff tool's description comes from the target's description, so this line steers the choice.
        description="Finds information in the filing and answers questions it states directly.",
        instructions=QUICK_BROKEN if BREAK else QUICK,
        tools=tools, default_options=AGENT_DEFAULTS,
        # Required by HandoffBuilder (MAF 1.20): history is saved after every model call, so a handoff
        # that cuts a tool loop short leaves the conversation consistent for the next agent.
        require_per_service_call_history_persistence=True,
    )
    deep = Agent(
        client=get_client(), name="deep",
        description="Careful analyst for calculations, comparisons and judgements.",
        instructions=DEEP_BROKEN if BREAK else DEEP,
        tools=tools, default_options=AGENT_DEFAULTS | {"reasoning": {"effort": ANALYSIS_REASONING}},
        require_per_service_call_history_persistence=True,
    )
    builder = HandoffBuilder(participants=[quick, deep]).with_start_agent(quick)
    if BREAK:
        # No add_handoff = everyone can hand to everyone (mesh). Only our cap stops a ping-pong.
        return builder.with_termination_condition(lambda conv: handoffs(conv) >= MAX_HANDOFFS).build()
    # One way only: quick → deep. deep can't hand back, so they can't ping-pong.
    return builder.add_handoff(quick, [deep]).build()


async def main() -> None:
    rows = {r["id"]: r for r in map(json.loads, (SPLITS / "dev.jsonl").open())}
    for qid in IDS[2:3] if BREAK else IDS:  # break mode: just the Adobe ratio, which needs search AND math
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
        if BREAK:
            convo = [m for out in result.get_outputs() for m in out.messages]
            print(f"  handoffs: {handoffs(convo)} (cap {MAX_HANDOFFS})")


asyncio.run(main())
