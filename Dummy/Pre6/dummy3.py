import asyncio
import os
import random

from dotenv import load_dotenv

from picoagents import Agent
from picoagents.llm import AzureOpenAIChatCompletionClient
from picoagents.memory import ListMemory, MemoryContent

load_dotenv(dotenv_path="../.env")
try:
    from picoagents.memory import ChromaDBMemory

    HAS_CHROMADB = True
except ImportError:
    ChromaDBMemory = None  # type: ignore
    HAS_CHROMADB = False
    print("ChromaDB not available. Install with: pip install 'picoagents[rag]'")


async def list_memory_example():
    """Minimal ListMemory example."""
    print("=== LIST MEMORY EXAMPLE ===")

    # Create Azure client
    try:
        model_client = AzureOpenAIChatCompletionClient(
            model="gpt-4.1-mini",
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
    except Exception as e:
        print(f"Azure client setup failed: {e}")
        print("Make sure AZURE_OPENAI_ENDPOINT environment variable is set")
        return

    # Create memory and add a preference
    memory = ListMemory(max_memories=10)
    await memory.add(
        MemoryContent(
            content="User loves pirate-style responses", mime_type="text/plain"
        )
    )

    # Agent with memory
    agent = Agent(
        name="assistant",
        description="Helpful assistant with memory",
        instructions="You are helpful. Use any relevant context.",
        model_client=model_client,
        memory=memory,
    )

    response = await agent.run("What's 2+2?")
    print(f"Response: {response.messages[-1].content}")
    print(f"Memory items: {len(memory.memories)}")


async def chromadb_example():
    """Minimal ChromaDB semantic search example."""
    if not HAS_CHROMADB:
        print("\n=== CHROMADB NOT AVAILABLE ===")
        return

    print("\n=== CHROMADB SEMANTIC SEARCH EXAMPLE ===")

    # Create Azure client
    try:
        model_client = AzureOpenAIChatCompletionClient(
            azure_deployment="gpt-4.1-mini",
            azure_endpoint=os.environ.get(
                "AZURE_OPENAI_ENDPOINT", "https://your-endpoint.openai.azure.com/"
            ),
        )
    except Exception as e:
        print(f"Azure client setup failed: {e}")
        print("Make sure AZURE_OPENAI_ENDPOINT environment variable is set")
        return

    # Create ChromaDB memory
    if not HAS_CHROMADB or ChromaDBMemory is None:
        print("ChromaDB not available!")
        return
    memory = ChromaDBMemory(collection_name="demo", max_memories=100)

    # Add various facts
    facts = [
        "Alice works as a software engineer at TechCorp",
        "Bob is a data scientist who loves Python",
        "Charlie is a product manager focusing on AI products",
        "The office has a coffee machine on the 3rd floor",
    ]

    for fact in facts:
        await memory.add(MemoryContent(content=fact))

    # Test semantic search - query about "programming" should find Bob
    query_result = await memory.query("programming languages", limit=2)

    print(f"Query: 'programming languages'")
    print(f"Found {len(query_result.results)} relevant memories:")
    for i, result in enumerate(query_result.results, 1):
        print(f"  {i}. {result.content}")

    # Agent with semantic memory
    agent = Agent(
        name="assistant",
        description="Helpful assistant with semantic memory",
        instructions="Answer using relevant context from memory.",
        model_client=model_client,
        memory=memory,
    )

    response = await agent.run("Who knows about programming?")
    print(f"\nAgent response: {response.messages[-1].content}")


async def main():
    """Run both memory examples."""
    await list_memory_example()
    await chromadb_example()


if __name__ == "__main__":
    asyncio.run(main())
