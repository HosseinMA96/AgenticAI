"""Week 1 · Step 2 📘: first tool. Watch the model ask our code to do math (book 4.3–4.4)."""

import asyncio
from typing import Annotated, Literal

from agent_framework import Agent, tool
from pydantic import Field

from finsight.llm import get_client


# @tool turns this function into a JSON schema (name + docstring + typed params).
# That schema is ALL the model sees; it never sees the body.
@tool
def calculator(
    a: Annotated[float, Field(description="Left operand")],
    op: Literal["+", "-", "*", "/"],
    b: Annotated[float, Field(description="Right operand")],
) -> float | str:
    """Exact arithmetic on two numbers. Use this for any calculation instead of doing math yourself."""
    print(f"  🔧 tool called: {a} {op} {b}")  # proof that OUR process runs it
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    # The model can send b=0; returning an error string lets it see what went wrong and recover.
    if b == 0:
        return "error: division by zero"
    return a / b


agent = Agent(
    client=get_client(),
    name="analyst",
    instructions="You are a concise financial analyst. Use the calculator for every arithmetic step.",
    tools=[calculator],
)


async def main() -> None:
    response = await agent.run(
        "Revenue was $18,902.1M and net income was $2,413.7M. What is the net margin in percent?"
    )
    print(response.text)


asyncio.run(main())
