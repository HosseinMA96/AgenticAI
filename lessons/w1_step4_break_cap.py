"""Week 1 · Step 4 📘: break it. Cap the tool calls and see what the agent does (book 2.3–2.5)."""

import asyncio

from agent_framework import Agent, tool

from finsight.limits import count_tool_calls, limit_hit
from finsight.llm import get_client
from finsight.tools.calculator import evaluate


@tool
def calculator(expression: str) -> str:
    """Exact arithmetic. ONE operation per call, e.g. '2413.7 / 18902.1'."""
    print(f"  🔧 tool ran: {expression}")
    return str(evaluate(expression))


client = get_client()
# The cap: at most 1 tool run per agent.run(). Default is None (unlimited).
client.function_invocation_configuration["max_function_calls"] = 1

agent = Agent(
    client=client,
    name="analyst",
    instructions="You are a financial analyst. Use the calculator for every arithmetic step, one operation per call.",
    tools=[calculator],
)

QUESTION = (
    "Revenue was 96.0 in 2022 and 112.4 in 2023 and 143.0 in 2024. "
    "What is the growth rate 2022→2023, the growth rate 2023→2024, and the difference between them?"
)


async def main() -> None:
    response = await agent.run(QUESTION)
    print("\nAgent says:\n", response.text)
    # 🏗️ The D5 flag: our code can now tell this answer was cut short.
    print(f"\ntool calls: {count_tool_calls(response)}  limit_hit: {limit_hit(response, max_calls=1)}")
    # The truth, computed by us, to compare against.
    g1, g2 = 112.4 / 96.0 - 1, 143.0 / 112.4 - 1
    print(f"\nCorrect: {g1:.4%}, {g2:.4%}, difference {g2 - g1:.4%}")


asyncio.run(main())
