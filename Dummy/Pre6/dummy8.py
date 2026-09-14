"""
Computer Use Agent Example

This example demonstrates how to use the ComputerUseAgent to automate
web browser interactions using the tool-based approach.

The ComputerUseAgent uses the base Agent's proven tool calling mechanism
with specialized Playwright tools for web automation.
"""

import asyncio
import os

from dotenv import load_dotenv

from picoagents.agents import ComputerUseAgent, PlaywrightWebClient
from picoagents.llm import AzureOpenAIChatCompletionClient

load_dotenv(dotenv_path="../.env")


async def basic_example():
    """
    Basic Example: Navigate to a website and extract information.

    This example shows how to:
    1. Create a ComputerUseAgent with Playwright web automation
    2. Use the agent to navigate to a website
    3. Extract specific information from the page
    4. Print a paragraph summary of general tech vibe based on all of your observations
    """
    print("=" * 60)
    print("COMPUTER USE AGENT - BASIC EXAMPLE")
    print("=" * 60)

    # 1. Create the LLM client
    # The ComputerUseAgent uses GPT-4.1-mini for reliable tool calling
    model_client = AzureOpenAIChatCompletionClient(
        model="gpt-4.1-mini",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )

    # 2. Create the ComputerUseAgent with async context manager for automatic cleanup
    # This agent inherits from the base Agent and adds web automation tools
    async with ComputerUseAgent(
        interface_client=PlaywrightWebClient(headless=False),  # Headless browser
        model_client=model_client,
        max_actions=10,  # Limit actions to prevent runaway execution
        use_screenshots=True,  # Enable screenshots for LLM vision and UI display
    ) as computer_agent:
        print("✅ ComputerUseAgent created successfully")

        # 3. Execute a web automation task
        # The agent will use tools like navigate, observe_page, click, type, etc.
        task = "what is the latest AI news on techcrunch.com. Summarize it as a nice bulleted list. Also dig into the first 3 articles and summarize it in a few sentences."

        print(f"\n🎯 Task: {task}")
        print("\n📋 Execution Log:")
        print("-" * 40)

        try:
            # 4. Stream execution with real-time updates
            async for event in computer_agent.run_stream(task):
                print(event)

        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()

    # Browser automatically closed here


if __name__ == "__main__":
    print("🚀 ComputerUseAgent Example")
    print("   Using tool-based approach with base Agent inheritance")

    # Run the basic example
    asyncio.run(basic_example())

    print("\n✅ Example completed!")
