"""Week 3, Step 8 (lesson): mid-run cancellation (book Ch 7, 4.13).

The ping chat from step 6, started as a task. After ping 2 we call task.cancel(), as a user pressing Stop would.
Questions: does the run stop at once? Do pings keep happening afterwards (a leaked background task)?

Run: uv run python lessons/w3_step8_cancel.py
"""

import asyncio

from agent_framework import Agent, tool
from agent_framework.orchestrations import GroupChatBuilder

from finsight.config import CHEAP_MODEL
from finsight.llm import AGENT_DEFAULTS, get_client

calls = {"n": 0}
second_ping = asyncio.Event()


@tool
async def ping() -> str:
    """Returns pong. Call it as often as you are asked to."""
    calls["n"] += 1
    print("  ping", calls["n"], flush=True)
    if calls["n"] == 2:
        second_ping.set()
    try:
        await asyncio.sleep(5)  # a tool that takes a moment, so a cancel can land inside it
    except asyncio.CancelledError:
        print(f"  ping {calls['n']} was interrupted mid-run by the cancel", flush=True)
        raise  # always re-raise, or the cancel is swallowed
    return f"pong #{calls['n']}"


async def main() -> None:
    agents = [Agent(client=get_client(CHEAP_MODEL), name=n, tools=[ping], default_options=AGENT_DEFAULTS,
                    instructions="Call the ping tool 5 times, one call after another, then say 'done'.")
              for n in ("a", "b")]
    workflow = GroupChatBuilder(participants=agents, max_rounds=6,
                                selection_func=lambda s: "a" if s.current_round % 2 == 0 else "b").build()
    task = asyncio.create_task(workflow.run("Start."))
    await second_ping.wait()
    task.cancel()
    print("cancel() called after ping 2")
    try:
        await task
    except asyncio.CancelledError:
        print("task ended with CancelledError")
    at_cancel = calls["n"]
    await asyncio.sleep(15)  # would a leaked background task keep pinging?
    print(f"pings at cancel={at_cancel}, 15 s later={calls['n']} →", "leaked" if calls["n"] > at_cancel else "clean stop")


asyncio.run(main())
