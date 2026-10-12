"""Week 2, Step 3 (lesson): session memory, and where the history lives (book 4.7).

The same two turns, without and with a session. The facts are in turn 1,
so no tools are needed.

Run: uv run python lessons/w2_step3_session.py
"""

import asyncio

from agent_framework import Agent

from finsight.llm import get_client

TURN_1 = "Adobe's revenue was $4,796M in 2015 and $4,147M in 2014. What was 2015 revenue?"
TURN_2 = "And 2014?"  # only makes sense if turn 1 is remembered

agent = Agent(client=get_client(), name="analyst", instructions="You are a concise financial analyst.")


def tokens_in(response) -> int:
    return (response.usage_details or {}).get("input_token_count")


async def main() -> None:
    print("=== without a session: every run() starts blank ===")
    await agent.run(TURN_1)
    r = await agent.run(TURN_2)
    print(f"turn 2: {r.text!r}  (input tokens: {tokens_in(r)})\n")

    print("=== with a session ===")
    session = agent.create_session()
    await agent.run(TURN_1, session=session)
    r = await agent.run(TURN_2, session=session)
    print(f"turn 2: {r.text!r}  (input tokens: {tokens_in(r)})\n")

    # Where does the history live? Service-side: an ID pointing at Azure's copy.
    # Client-side: the messages themselves, inside session.state.
    print("service_session_id:", session.service_session_id)
    print("session.state keys:", list(session.state))

    print("\n=== with a session, store=False: history kept on our side ===")
    # store=False tells Azure not to keep the response. With nothing stored
    # service-side, MAF adds an InMemoryHistoryProvider that keeps the messages
    # in session.state and re-sends them on every call.
    local = Agent(
        client=get_client(), name="analyst", instructions="You are a concise financial analyst.",
        default_options={"store": False},
    )
    session = local.create_session()
    await local.run(TURN_1, session=session)
    r = await local.run(TURN_2, session=session)
    print(f"turn 2: {r.text!r}  (input tokens: {tokens_in(r)})\n")
    print("service_session_id:", session.service_session_id)
    for key, value in session.state.items():
        print(f"session.state[{key!r}]:", value if not isinstance(value, dict) else {k: type(v).__name__ for k, v in value.items()})


asyncio.run(main())
