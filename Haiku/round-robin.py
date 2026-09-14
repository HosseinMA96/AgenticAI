#!/usr/bin/env python3
"""
Simple round-robin orchestration example.

Run in CLI mode (default):
    python examples/orchestration/round-robin.py

Run with Web UI:
    python examples/orchestration/round-robin.py --web
"""

import argparse
import asyncio
import os
from dotenv import load_dotenv

from picoagents import Agent
from picoagents.llm import AzureOpenAIChatCompletionClient
from picoagents.orchestration import RoundRobinOrchestrator
from picoagents.termination import MaxMessageTermination, TextMentionTermination

load_dotenv(dotenv_path="../.env")


def get_orchestrator():
    """Demonstrate round-robin conversation flow."""

    # client = OpenAIChatCompletionClient(model="gpt-4.1-mini")
    client = AzureOpenAIChatCompletionClient(
        model="gpt-4.1-mini",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )

    # Create a haiku writer and critic working together
    poet = Agent(
        name="poet",
        description="Haiku poet.",
        instructions="""You are a haiku poet.""",
        model_client=client,
    )

    critic = Agent(
        name="critic",
        description="Poetry critic who provides specific, constructive feedback on haikus.",
        instructions="""You are a haiku critic. When you see a haiku, provide 2-3 specific, 
        actionable suggestions for improvement. Focus on imagery, syllable count, seasonal words, 
        or emotional impact. Be constructive and brief. If you are satisfied with the haiku and your comments addressed, respond with the word 'APPROVED'""",
        model_client=client,
    )
    termination = MaxMessageTermination(max_messages=8) | TextMentionTermination(
        text="APPROVED"
    )
    # Create orchestrator - poet writes first, then critic provides feedback
    orchestrator = RoundRobinOrchestrator(
        agents=[poet, critic], termination=termination, max_iterations=4
    )

    return orchestrator


orchestrator = get_orchestrator()


async def main():
    task = "Write a haiku about cherry blossoms in spring"
    print(f"🎯 Task: {task}")
    print("🔄 Poet and Critic collaboration:\n")

    # Run orchestration and show final conversation
    stream = orchestrator.run_stream(task)

    async for message in stream:
        print(f"========\n{message}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Round-robin orchestration example with poet and critic agents"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch Web UI instead of CLI mode",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8070,
        help="Port for Web UI (default: 8070)",
    )
    args = parser.parse_args()

    if args.web:
        # Import WebUI only if needed
        from picoagents.webui import serve

        print("🚀 Starting PicoAgents WebUI with round-robin orchestrator...")
        print(f"\n📋 Poet & Critic Collaboration")
        print(f"  • Port: {args.port}")
        print(f"  • Try: 'Write a haiku about cherry blossoms in spring'\n")

        serve(
            entities=[orchestrator],
            port=args.port,
            auto_open=True,
        )
    else:
        # Run in CLI mode
        asyncio.run(main())
