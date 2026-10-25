"""Week 3, Step 6 (lesson): what do our tool-call limits cover, one agent turn or the whole chat? (D5, book Ch 7)

Two agents in a group chat, each told to call `ping` 5 times. The client cap is 3 function calls.
If the cap covered the whole chat, `ping` runs at most 3 times in total. If it resets on every
turn, we expect about 3 per turn.

Run: uv run python lessons/w3_step6_limit_scope.py
"""

import asyncio

from agent_framework import Agent, tool
from agent_framework.orchestrations import GroupChatBuilder

from finsight.config import CHEAP_MODEL
from finsight.llm import AGENT_DEFAULTS, get_client

CAP = 3
ROUNDS = 4
calls = {"n": 0}


@tool
def ping() -> str:
    """Returns pong. Call it as often as you are asked to."""
    calls["n"] += 1
    print("  ping", calls["n"], flush=True)
    return f"pong #{calls['n']}"


def agent(name: str) -> Agent:
    client = get_client(CHEAP_MODEL)
    client.function_invocation_configuration["max_function_calls"] = CAP
    return Agent(client=client, name=name, tools=[ping], default_options=AGENT_DEFAULTS,
                 instructions="Call the ping tool 5 times, one call after another, then say 'done'.")


async def main() -> None:
    workflow = GroupChatBuilder(
        participants=[agent("a"), agent("b")],
        selection_func=lambda s: "a" if s.current_round % 2 == 0 else "b",
        max_rounds=ROUNDS,
    ).build()
    await asyncio.wait_for(workflow.run("Start."), 90)
    print(f"cap per client = {CAP}, turns = {ROUNDS}, total ping calls = {calls['n']}")
    print("→ per turn" if calls["n"] > CAP else "→ whole chat")


asyncio.run(main())
