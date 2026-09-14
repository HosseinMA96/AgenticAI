"""
Examples from Chapter 4: Building Agents from Scratch
Demonstrates the three middleware examples from the book.
"""

import asyncio
import os
import re

from picoagents import (
    Agent,
    BaseMiddleware,
    LoggingMiddleware,
    PIIRedactionMiddleware,
    RateLimitMiddleware,
)
import asyncio
import os
import random

from dotenv import load_dotenv

from picoagents import Agent, AgentContext
from picoagents.llm import AzureOpenAIChatCompletionClient
from picoagents.memory import ListMemory, MemoryContent
from picoagents.tools import MemoryTool


load_dotenv(dotenv_path="../.env")

model_client = AzureOpenAIChatCompletionClient(
    model="gpt-4.1-mini", 
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY")
)


async def demo_code_review_with_memory():
    """
    Demonstrate memory tool with a code review scenario.

    Session 1: Agent reviews code with a bug, stores pattern
    Session 2: Agent reviews similar code, applies learned pattern
    """
    # Initialize model client
    client = AzureOpenAIChatCompletionClient(
        model="gpt-4.1-mini",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY")
    )

    # Create memory tool
    memory = MemoryTool(base_path="./demo_memory")

    # Create agent with memory tool
    agent = Agent(
        name="code_reviewer",
        description="Expert code reviewer who learns from past reviews",
        instructions="""You are an expert code reviewer.

IMPORTANT: ALWAYS check your memory directory at the start
of each review using the memory tool:
  memory(command="view", path="/memories")

When you find important patterns or bugs, store them in memory
for future reference using:
  memory(command="create", path="/memories/patterns/bug_name.md", file_text="...")

Apply learned patterns from memory to new code reviews.""",
        model_client=model_client,
        tools=[memory],
    )

    print("=" * 60)
    print("SESSION 1: Learning from a race condition bug")
    print("=" * 60)
    print()

    # Session 1: Review code with thread safety issue
    code_with_bug = '''
class WebScraper:
    def __init__(self):
        self.results = []  # Shared state!

    def scrape_urls(self, urls):
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.fetch, url) for url in urls]
            for future in as_completed(futures):
                self.results.append(future.result())  # RACE CONDITION!
        return self.results
'''

    task1 = f"""Review this multi-threaded code. The user reports
inconsistent results - sometimes fewer results than expected.

```python
{code_with_bug}
```

Find the bug and store the pattern in memory for future reference."""

    # Run agent
    response = await agent.run(task1)

    print(f"\n{agent.name}: {response.messages[-1].content}\n")
    print(f"Tool calls: {response.usage.tool_calls}")
    print()

    print("=" * 60)
    print("SESSION 2: Applying learned pattern (new conversation)")
    print("=" * 60)
    print()

    # Session 2: NEW conversation with similar async bug
    # Reset agent context to simulate new session
    agent.context = AgentContext()

    similar_code = '''
class APIClient:
    def __init__(self):
        self.responses = []
        self.error_count = 0

    async def fetch_all(self, endpoints):
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch(session, ep) for ep in endpoints]
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if "error" in result:
                    self.error_count += 1  # RACE!
                else:
                    self.responses.append(result)  # RACE!
        return self.responses
'''

    task2 = f"""Review this async API client code:

```python
{similar_code}
```"""

    response = await agent.run(task2)

    print(f"\n{agent.name}: {response.messages[-1].content}\n")
    print(f"Tool calls: {response.usage.tool_calls}")
    print()

    print("=" * 60)
    print("Notice how the agent:")
    print("1. Checked memory first (view /memories)")
    print("2. Found the thread-safety pattern from Session 1")
    print("3. Applied it immediately to async code in Session 2")
    print("=" * 60)


async def demo_memory_operations():
    """Demonstrate all memory tool operations."""
    print("\n" + "=" * 60)
    print("MEMORY TOOL OPERATIONS DEMO")
    print("=" * 60)
    print()

    client = AzureOpenAIChatCompletionClient(
        model="gpt-4.1-mini",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY")
    )
    memory = MemoryTool(base_path="./demo_memory_ops")

    agent = Agent(
        name="assistant",
        description="Helpful assistant with memory",
        instructions="""You are a helpful assistant.
Use the memory tool to store and organize information.

Available commands:
- view: Show directory or file contents
- create: Create a new file
- str_replace: Edit file by replacing text
- insert: Insert text at a specific line
- delete: Remove a file or directory
- rename: Rename or move a file
""",
        model_client=client,
        tools=[memory],
    )

    tasks = [
        "Check what's in your memory directory",
        "Create a file at /memories/notes.md with content 'Meeting notes:\n- Discussed project timeline\n- Next steps defined'",
        "View the notes.md file you just created",
        "Update the notes.md file by replacing '- Next steps defined' with '- Next steps: Start implementation on Monday'",
        "Insert a new line at line 2 in notes.md with content '- Team: Alice, Bob, Carol\n'",
        "View the updated notes.md file",
    ]

    for i, task in enumerate(tasks, 1):
        print(f"\n📝 Task {i}: {task}")
        response = await agent.run(task)
        print(f"✅ {agent.name}: {response.messages[-1].content}")

    print("\n" + "=" * 60)
    print("All operations completed successfully!")
    print("=" * 60)


async def demo_memory_organization():
    """Demonstrate organizing memory with directories."""
    print("\n" + "=" * 60)
    print("MEMORY ORGANIZATION DEMO")
    print("=" * 60)
    print()

    client = AzureOpenAIChatCompletionClient(
        model="gpt-4.1-mini",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY")
    )
    memory = MemoryTool(base_path="./demo_memory_org")

    agent = Agent(
        name="assistant",
        description="Assistant with organized memory",
        instructions="""You are an organized assistant.
Structure your memory into logical directories:
- /memories/patterns/ - Code patterns and best practices
- /memories/bugs/ - Known bugs and fixes
- /memories/users/ - User preferences
- /memories/projects/ - Project-specific notes
""",
        model_client=client,
        tools=[memory],
    )

    tasks = [
        "Create a file at /memories/patterns/singleton.md with notes about the singleton pattern",
        "Create a file at /memories/bugs/race_condition.md with notes about thread safety",
        "Create a file at /memories/users/preferences.md with user preferences",
        "Show me the structure of my memory directory",
        "Show me what's in the patterns directory",
    ]

    for task in tasks:
        print(f"\n📝 {task}")
        response = await agent.run(task)
        print(f"✅ {response.messages[-1].content[:200]}...")

    print("\n" + "=" * 60)
    print("Memory is now organized by category!")
    print("=" * 60)


if __name__ == "__main__":
    print("🧠 PicoAgents Memory Tool Examples\n")

    # Run demos
    asyncio.run(demo_code_review_with_memory())
    asyncio.run(demo_memory_operations())
    asyncio.run(demo_memory_organization())

    print("\n✨ All examples completed!")
