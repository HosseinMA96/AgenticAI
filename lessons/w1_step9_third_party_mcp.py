"""Week 1 · Step 9 📘: a third-party MCP server. We didn't write it, yet the agent can use it (book 12.2, D13).

Tool discovery: on connect, MAF asks the server "what tools do you have?" and turns each
answer (name + description + JSON schema) into a tool. That description is ALL the model
knows about it, exactly like our own @tool functions (Step 2).
"""

import asyncio
import json

from agent_framework import Agent, MCPStdioTool

from finsight.llm import get_client

# Pinned version: we run someone else's code, so we choose when it changes (D13).
fetch = MCPStdioTool(name="fetch", command="uvx", args=["mcp-server-fetch==2026.8.18"])


async def main() -> None:
    async with fetch:
        # 1. Discovery: what did the server tell us about itself?
        for f in fetch.functions:
            print(f"🔎 discovered tool: {f.name}\n   description: {f.description[:300]}...")
            print(f"   parameters: {json.dumps(f.parameters(), indent=1)[:400]}\n")

        # 2. Use it: the model only has that description to go on.
        agent = Agent(client=get_client(), name="reader", instructions="Be concise.", tools=[fetch])
        r = await agent.run("Fetch https://en.wikipedia.org/wiki/EDGAR and tell me in one sentence what EDGAR is.")
        for m in r.messages:
            for c in m.contents:
                if c.type == "function_call":
                    print(f"🔧 {c.name}({c.arguments})")
        print("\n" + r.text)


asyncio.run(main())
