"""Week 3, Step 7 (lesson): the same ping chat as step 6, now with ONE budget shared by both agents (D39).

Step 6: cap 3 per turn → 8 pings over 4 turns. Here: budget of 5 tool calls for the whole run.
Expect: exactly 5 pings, then the run stops with BudgetExceeded. Does the error reach us through the group chat?

Run: uv run python lessons/w3_step7_budget.py
"""

import asyncio

from agent_framework import Agent, tool
from agent_framework.orchestrations import GroupChatBuilder

from finsight.config import CHEAP_MODEL
from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.middleware.budget import RunBudget

calls = {"n": 0}


@tool
def ping() -> str:
    """Returns pong. Call it as often as you are asked to."""
    calls["n"] += 1
    print("  ping", calls["n"], flush=True)
    return f"pong #{calls['n']}"


async def main() -> None:
    budget = RunBudget(max_tool_calls=5, max_usd=0.5, max_seconds=90)
    agents = [Agent(client=get_client(CHEAP_MODEL), name=n, tools=[ping], default_options=AGENT_DEFAULTS,
                    middleware=budget.middleware(),  # the same budget object on every agent
                    instructions="Call the ping tool 5 times, one call after another, then say 'done'.")
              for n in ("a", "b")]
    workflow = GroupChatBuilder(participants=agents, max_rounds=6,
                                selection_func=lambda s: "a" if s.current_round % 2 == 0 else "b").build()
    try:
        await workflow.run("Start.")
        print("finished normally")
    except BaseException as e:  # noqa: BLE001 - we want to see exactly what arrives
        print(f"stopped by {type(e).__name__}: {str(e)[:150]}  cause={type(e.__cause__).__name__}")
    print(f"pings={calls['n']}, tool_calls counted={budget.tool_calls}, spent=${budget.spent_usd:.4f}")


asyncio.run(main())
