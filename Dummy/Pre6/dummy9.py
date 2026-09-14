import asyncio
import os

from dotenv import load_dotenv

from picoagents.agents import ComputerUseAgent, PlaywrightWebClient
from picoagents.llm import AzureOpenAIChatCompletionClient

load_dotenv(dotenv_path="../.env")


async def main():
    # Create agent with multimodal reasoning capabilities
    model_client = AzureOpenAIChatCompletionClient(
        model="gpt-4.1-mini",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )

    async with ComputerUseAgent(
        interface_client=PlaywrightWebClient(headless=False),
        model_client=model_client,
        use_screenshots=True,
        max_actions=10
    ) as computer_agent:
        task = "What is the latest AI news on techcrunch.com?"
        async for event in computer_agent.run_stream(task):
            print(event)


if __name__ == "__main__":
    asyncio.run(main())
