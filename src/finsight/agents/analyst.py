"""The first FinSight agent: one analyst with search, page-image and calculator tools (D10)."""

from pathlib import Path

from agent_framework import Agent, AgentResponse, MCPStdioTool, MCPStreamableHTTPTool

from finsight.llm import get_client
from finsight.models import Answer
from finsight.tools.calculator import calculator
from finsight.tools.filings import render_page, search_filing_text

# Prompts live in .md files so a prompt change shows up as a diff (CLAUDE.md).
_PROMPTS = Path(__file__).parents[1] / "prompts"


def edgar_stdio() -> MCPStdioTool:
    """Our edgar-mcp server, started as a child process and spoken to over stdin/stdout (book 12.2).
    Use as `async with edgar_stdio() as edgar:` so the process is stopped afterwards."""
    return MCPStdioTool(name="edgar", command="uv", args=["run", "python", "-m", "finsight.mcp_edgar"], load_prompts=False)


def edgar_http(url: str = "http://127.0.0.1:8000/mcp") -> MCPStreamableHTTPTool:
    """The same server, already running on its own (`python -m finsight.mcp_edgar --http`)."""
    return MCPStreamableHTTPTool(name="edgar", url=url, load_prompts=False)


def build_analyst(*extra_tools, prompt: str = "analyst") -> Agent:
    """prompt: a file name in prompts/ without .md, so eval configs can swap prompts."""
    return Agent(
        client=get_client(),
        name="analyst",
        instructions=(_PROMPTS / f"{prompt}.md").read_text(),
        tools=[search_filing_text, render_page, calculator, *extra_tools],
    )


async def ask(agent: Agent, doc_name: str, question: str) -> AgentResponse:
    """Run one question. response.value is the typed Answer."""
    return await agent.run(f"Filing: {doc_name}\n\nQuestion: {question}", options={"response_format": Answer})


async def _main(doc_name: str, question: str, http: bool) -> None:
    async with edgar_http() if http else edgar_stdio() as edgar:
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

    http = "--http" in sys.argv  # connect to an already-running edgar-mcp instead of starting one
    args = [a for a in sys.argv[1:] if a != "--http"]
    if len(args) != 2:
        sys.exit('usage: python -m finsight.agents.analyst [--http] <FILING_ID> "<question>"   (filing ids: ls data/pdfs)')
    asyncio.run(_main(args[0], args[1], http))
