"""The first FinSight agent: one analyst with search, page-image and calculator tools (D10)."""

from pathlib import Path

from agent_framework import Agent, AgentResponse, MCPStdioTool

from finsight.llm import get_client
from finsight.models import Answer
from finsight.tools.calculator import calculator
from finsight.tools.filings import render_page, search_filing_text

# Prompts live in .md files so a prompt change shows up as a diff (CLAUDE.md).
_PROMPT = (Path(__file__).parents[1] / "prompts" / "analyst.md").read_text()


def edgar_stdio() -> MCPStdioTool:
    """Our edgar-mcp server, started as a child process and spoken to over stdin/stdout (book 12.2).
    Use as `async with edgar_stdio() as edgar:` so the process is stopped afterwards."""
    return MCPStdioTool(name="edgar", command="uv", args=["run", "python", "-m", "finsight.mcp_edgar"], load_prompts=False)


def build_analyst(*extra_tools) -> Agent:
    return Agent(
        client=get_client(),
        name="analyst",
        instructions=_PROMPT,
        tools=[search_filing_text, render_page, calculator, *extra_tools],
    )


async def ask(agent: Agent, doc_name: str, question: str) -> AgentResponse:
    """Run one question. response.value is the typed Answer."""
    return await agent.run(f"Filing: {doc_name}\n\nQuestion: {question}", options={"response_format": Answer})


async def _main(doc_name: str, question: str) -> None:
    async with edgar_stdio() as edgar:
        response = await ask(build_analyst(edgar), doc_name, question)
    # Show the searches too, so you can watch the agent work.
    for m in response.messages:
        for c in m.contents:
            if c.type == "function_call":
                print(f"🔧 {c.name}({c.arguments})")
    print(response.value.model_dump_json(indent=2))


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) != 3:
        sys.exit('usage: python -m finsight.agents.analyst <FILING_ID> "<question>"   (filing ids: ls data/pdfs)')
    asyncio.run(_main(sys.argv[1], sys.argv[2]))
