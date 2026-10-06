"""Week 1 · Step 1: hello agent. One agent, no tools."""

import asyncio

from agent_framework import Agent

from finsight.llm import get_client

# The client knows HOW to talk to the model. It now comes from the product (Step 1 🏗️).
client = get_client()

# The agent adds WHO it is: a name and instructions (the system prompt).
agent = Agent(
    client=client,
    name="hello",
    instructions="You are a concise financial analyst. Answer in at most 2 sentences.",
)


async def main() -> None:
    response = await agent.run("What is a 10-K filing?")
    print(response.text)


asyncio.run(main())
