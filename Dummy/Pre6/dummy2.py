"""
Basic Agent Example - Simplified and WebUI discoverable

This example demonstrates creating a simple agent with tools.
The agent is defined at module level, making it discoverable by picoagentsui.

Run standalone: python examples/agents/basic-agent.py
Or discover via: picoagentsui --dir examples/agents
"""

import asyncio
import os
import random

from dotenv import load_dotenv

from picoagents import Agent
from picoagents.llm import AzureOpenAIChatCompletionClient

load_dotenv(dotenv_path="../.env")


def get_weather(location: str) -> str:
    """Get current weather for a given location."""
    return f"The weather in {location} is sunny, 75°F"


def calculate(expression: str) -> str:
    """Perform basic mathematical calculations."""
    try:
        result = eval(expression)
        return f"The result of {expression} is {result}"
    except Exception as e:
        return f"Error calculating {expression}: {e}"

client = AzureOpenAIChatCompletionClient(
    model="gpt-4.1-mini",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

agent = Agent(
    name="basic_assistant",
    description="A helpful assistant with weather and calculator tools",
    instructions="You are a helpful assistant with access to weather and calculation tools. Use them when appropriate.",
    model_client=client,
    tools=[get_weather, calculate],
    example_tasks=[
        "What's the weather in San Francisco?",
        "Calculate 125 * 48",
        "What's the weather in Tokyo and what's 15% of 240?",
        "Is it sunny in London?",
    ],
)


async def main():
    """Run example interactions with the agent."""
    print("=== Basic Agent Example ===\n")

    print(f"Agent: {agent.name}")
    print(f"Tools: {[tool.name for tool in agent.tools]}\n")

    async for event in agent.run_stream(
        "What's the weather in New York and what is 12 * 15?", stream_tokens=False
    ):
        print(event)


if __name__ == "__main__":
    asyncio.run(main())
