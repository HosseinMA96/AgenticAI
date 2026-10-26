"""Week 3, Step 10 (lesson): break it: no termination at all, watch the loop run away (book Ch 7).

Step 9's maker + stubborn checker, but with no max_rounds and no termination_condition. MAF's default
for both is None, so nothing inside the framework will ever end this chat. The only stop is a
wall-clock timeout OUTSIDE the framework (asyncio.wait_for), our fail-safe (option A).
A RunBudget with no limits is used only as a meter, to show what the runaway cost.

Run: uv run python lessons/w3_step10_runaway.py
"""

import asyncio
import time

from agent_framework import Agent, ChatContext, chat_middleware
from agent_framework.orchestrations import GroupChatBuilder

from finsight.config import CHEAP_MODEL
from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.middleware.budget import RunBudget

MAKER = "You write one short sentence about the weather."
STUBBORN = "Reply with one short objection to the previous message. Never say APPROVED."
TIMEOUT_S = 20

turns = {"n": 0}
started = time.monotonic()


def print_turns(name: str):
    @chat_middleware
    async def show(context: ChatContext, call_next) -> None:
        await call_next()
        turns["n"] += 1
        text = context.result.text if context.result is not None else ""
        print(f"  {time.monotonic() - started:5.1f} s  turn {turns['n']:3d}  {name:7s} {text[:70]!r}", flush=True)
    return show


async def main() -> None:
    meter = RunBudget()  # no limits: it only counts
    agents = [Agent(client=get_client(CHEAP_MODEL), name=n, instructions=p, default_options=AGENT_DEFAULTS,
                    middleware=[print_turns(n), *meter.middleware()])
              for n, p in (("maker", MAKER), ("checker", STUBBORN))]
    workflow = GroupChatBuilder(  # no max_rounds, no termination_condition
        participants=agents,
        selection_func=lambda s: "maker" if s.current_round % 2 == 0 else "checker",
    ).build()
    try:
        await asyncio.wait_for(workflow.run("Start."), timeout=TIMEOUT_S)
        print("the chat ended on its own (unexpected)")
    except TimeoutError:
        print(f"fail-safe fired after {TIMEOUT_S} s: the chat never stopped on its own")
    print(f"{turns['n']} turns, ${meter.spent_usd:.4f}, ~{turns['n'] / TIMEOUT_S:.1f} turns/s")
    print(f"at this rate, 1 hour unattended ≈ {turns['n'] * 3600 / TIMEOUT_S:.0f} turns, "
          f"${meter.spent_usd * 3600 / TIMEOUT_S:.2f} (and each turn's prompt grows, so really more)")


asyncio.run(main())
