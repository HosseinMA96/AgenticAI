"""
Example: Agent with OpenTelemetry instrumentation.

This demonstrates automatic telemetry collection using environment variables.
Traces and metrics are automatically exported to Jaeger.

Setup:
1. Start Jaeger: docker-compose up -d
2. Set environment variables (see below)
3. Run this script
4. View traces at http://localhost:16686

Environment Variables:
- PICOAGENTS_ENABLE_OTEL: Enable/disable telemetry (default: false)
- OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint URL (default: http://localhost:4318)
- OTEL_SERVICE_NAME: Service name in traces (default: picoagents)
- OTEL_METRICS_ENABLED: Enable metrics export (default: false, Jaeger doesn't support metrics)
- PICOAGENTS_OTEL_CAPTURE_CONTENT: Capture prompts/completions (default: false, opt-in for privacy)
"""

import os

from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

# Enable OpenTelemetry (MUST be set before importing picoagents)
os.environ["PICOAGENTS_ENABLE_OTEL"] = "true"
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
os.environ["OTEL_SERVICE_NAME"] = "picoagents-example"

# Opt-in to capture message content (prompts/completions)
# WARNING: May contain sensitive information - disabled by default
os.environ["PICOAGENTS_OTEL_CAPTURE_CONTENT"] = "true"

from picoagents import Agent  # noqa: E402
from picoagents.llm import AzureOpenAIChatCompletionClient  # noqa: E402
from picoagents.tools import FunctionTool  # noqa: E402


def get_weather(location: str) -> str:
    """Get the weather for a location."""
    return f"The weather in {location} is sunny and 72°F"


def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression."""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {e}"


async def main():
    """Run agent with automatic telemetry."""
    # Get Azure credentials
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not api_key or not endpoint:
        print("Please set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables")
        return

    # Create model client
    model = AzureOpenAIChatCompletionClient(
        model="gpt-4.1-mini",
        api_key=api_key,
        azure_endpoint=endpoint
    )

    # Create agent with tools
    agent = Agent(
        name="weather_assistant",
        description="An assistant that can check weather and do calculations",
        instructions="You are a helpful assistant. Use tools to answer questions.",
        model_client=model,
        tools=[
            FunctionTool(get_weather),
            FunctionTool(calculate),
        ],
    )

    # Run queries - telemetry automatically collected!
    queries = [
        "What's the weather in San Francisco?",
        "What is 42 * 137?",
        "What's the weather in Tokyo and what is 100 + 50?",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")

        response = await agent.run(query)

        print(f"\nResponse: {response.messages[-1].content}")
        print(f"Usage: {response.usage}")

    print(f"\n{'='*60}")
    print("✅ Done! View traces at: http://localhost:16686")
    print("   Search for service: picoagents-example")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
