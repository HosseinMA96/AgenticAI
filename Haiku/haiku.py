import asyncio
from picoagents import Agent
import os
from dotenv import load_dotenv
from picoagents.llm import AzureOpenAIChatCompletionClient
from picoagents.webui import serve

load_dotenv(dotenv_path="../.env")

# Setup the language model client
client = AzureOpenAIChatCompletionClient(
    model="gpt-4.1-mini",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

# Create a haiku poet
poet = Agent(
    name="poet",
    description="Haiku poet.",
    instructions="You are a haiku poet.",
    model_client=client
)

# Create a poetry critic
critic = Agent(
    name="critic",
    description="Poetry critic who provides constructive feedback on haikus.",
    instructions="You are a haiku critic. \
When you see a haiku, provide 2-3 specific, actionable \
suggestions for improvement. . Be constructive and brief. \
If satisfied with the haiku, respond with 'APPROVED'",
    model_client=client
)


# Test the poet
async def test_poet():
    response = await poet.run("Write a haiku about cherry blossoms in spring")
    print(f"Poet says:\n{response.final_content}")

# Test the critic
async def test_critic():
    haiku = ("Cherry blossoms fall\n"
    "Petals dancing in spring breeze\n"
    "Nature's gentle song")
    response = await critic.run(f"Please critique this haiku: {haiku}")
    print(f"Critic says: {response}")

from picoagents.orchestration import 1
from picoagents.termination import MaxMessageTermination, TextMentionTermination
# Create termination conditions
termination = (MaxMessageTermination(max_messages=8) | TextMentionTermination(text="APPROVED"))

# Create the orchestrator
orchestrator = RoundRobinOrchestrator(
agents=[poet, critic],
termination=termination,
max_iterations=4
)

async def run_orchestration():
    task = "Write a haiku about cherry blossoms in spring"
    stream = orchestrator.run_stream(task)
    async for message in stream:
        print(f"{message}")


if __name__ == "__main__":
    # asyncio.run(test_poet())
    # asyncio.run(test_critic())
    # asyncio.run(run_orchestration())
    serve(entities=[orchestrator], port=8070, auto_open=True)