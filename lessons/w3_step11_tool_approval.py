"""Week 3, Step 11 (lesson): a tool that needs a human's yes before it runs (book 4.13, D40).

save_report writes a file: a side effect, like the Bcdr agent posting a comment. With
approval_mode="always_require" the framework does NOT run it; run() returns early with a request.
We answer it with a second run() on the same session. Run twice: once approve, once reject.

Run: uv run python lessons/w3_step11_tool_approval.py
"""

import asyncio
from pathlib import Path
from typing import Annotated

from agent_framework import Agent, Message, tool
from pydantic import Field

from finsight.config import CHEAP_MODEL
from finsight.llm import AGENT_DEFAULTS, get_client

OUT = Path(__file__).parent / "_out"
TASK = "Write a one-line report saying Adobe's FY2022 revenue was $17.6B, then save it as adobe.txt."


@tool(approval_mode="always_require")
def save_report(
    filename: Annotated[str, Field(description="File name, e.g. report.txt")],
    text: Annotated[str, Field(description="The report text")],
) -> str:
    """Save a report to disk."""
    OUT.mkdir(exist_ok=True)
    (OUT / Path(filename).name).write_text(text)  # .name: the model must not choose the folder
    print(f"  🔧 save_report ran: wrote {filename}")
    return f"saved {filename}"


async def run_once(approve: bool) -> None:
    agent = Agent(client=get_client(CHEAP_MODEL), name="writer", tools=[save_report],
                  default_options=AGENT_DEFAULTS, instructions="You write short reports and save them.")
    session = agent.create_session()  # the paused call lives in this session's history
    result = await agent.run(TASK, session=session)

    while result.user_input_requests:  # the run paused: the model asked for a tool that needs approval
        answers = []
        for req in result.user_input_requests:
            print(f"  ⏸  agent wants {req.function_call.name}({req.function_call.arguments})")
            print(f"  👤 human says: {'yes' if approve else 'no'}")
            answers.append(req.to_function_approval_response(approved=approve))
        result = await agent.run(Message("user", answers), session=session)

    print(f"  agent's final words: {result.text!r}")


async def main() -> None:
    for approve in (True, False):
        (OUT / "adobe.txt").unlink(missing_ok=True)
        print(f"=== approve={approve} ===")
        await run_once(approve)
        print(f"  file exists afterwards: {(OUT / 'adobe.txt').exists()}\n")


asyncio.run(main())
