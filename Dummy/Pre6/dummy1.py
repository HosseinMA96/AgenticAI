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

def get_temprature(city: str) -> str:
    """Get current weather for a given location."""
    return f"The get_temprature in {city} is sunny, 66°F"

def get_price(merchandise: str) -> str:
    """Get current weather for a given location."""
    return f"The price of {merchandise} is ${random.randint(1, 100)}"

# Create an agent with Azure OpenAI
client = AzureOpenAIChatCompletionClient(
    model="gpt-4.1-mini",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

agent = Agent(
    name="assistant",
    description="You are a helpful assistant.",
    instructions="You are helpful. Use tools when appropriate.",
    model_client=client,
    tools=[get_weather, get_price]  # Functions become tools automatically!
)

async def main():
    response = await agent.run("What's the weather in Paris?")
    print(f"Weather: {response.messages[-1].content}\n")

    response = await agent.run("What's the price of a pair of ladies tights?")
    print(f"Price: {response.messages[-1].content}")

if __name__ == "__main__":
    asyncio.run(main())
