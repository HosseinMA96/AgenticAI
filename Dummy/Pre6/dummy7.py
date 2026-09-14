"""
Example: Agent with content capture enabled.

This example demonstrates opt-in content capture for debugging.
WARNING: Prompts and completions may contain sensitive information.
Only enable in development/debugging scenarios.
"""

import os

from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

# Enable OpenTelemetry with content capture
os.environ["PICOAGENTS_ENABLE_OTEL"] = "true"
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
os.environ["OTEL_SERVICE_NAME"] = "picoagents-debug"

# OPT-IN: Capture prompts, completions, tool parameters and results
os.environ["PICOAGENTS_OTEL_CAPTURE_CONTENT"] = "true"

from picoagents import Agent  # noqa: E402
from picoagents.llm import AzureOpenAIChatCompletionClient  # noqa: E402
from picoagents.tools import FunctionTool  # noqa: E402


def get_weather(location: str) -> str:
    """Get the weather for a location."""
    return f"The weather in {location} is sunny and 72°F"


async def main():
    """Run agent with content capture enabled."""
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not api_key or not endpoint:
        print("Please set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables")
        return

    model = AzureOpenAIChatCompletionClient(
        model="gpt-4.1-mini",
        api_key=api_key,
        azure_endpoint=endpoint
    )

    agent = Agent(
        name="weather_debug",
        description="Weather assistant with full content logging",
        instructions="You are a helpful assistant. Use tools to answer questions.",
        model_client=model,
        tools=[FunctionTool(get_weather)],
    )

    # Single query for debugging
    query = "What's the weather in Paris?"
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}\n")

    response = await agent.run(query)

    print(f"Response: {response.messages[-1].content}")
    print(f"\n{'='*60}")
    print("✅ Done! View traces at: http://localhost:16686")
    print("   Search for service: picoagents-debug")
    print("   Check span attributes for gen_ai.input.messages and gen_ai.output.messages")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
