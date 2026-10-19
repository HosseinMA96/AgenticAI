"""The first FinSight agent: one analyst with search, page-image and calculator tools (D10, D24)."""

from pathlib import Path

from agent_framework import Agent, AgentResponse, MCPStdioTool, MCPStreamableHTTPTool, add_usage_details

from finsight.config import PAGE_FORMAT, SEARCH_MODE
from finsight.evidence import unread_citations
from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.memory.episodes import EpisodeStore, EpisodicMemory
from finsight.models import Answer
from finsight.rag.search import Mode
from finsight.tools.calculator import calculator
from finsight.tools.filings import render_page
from finsight.tools.search_filings import make_search_filings

# Prompts live in .md files so a prompt change shows up as a diff (CLAUDE.md).
_PROMPTS = Path(__file__).parents[1] / "prompts"


def edgar_stdio() -> MCPStdioTool:
    """Our edgar-mcp server, started as a child process and spoken to over stdin/stdout (book 12.2).
    Use as `async with edgar_stdio() as edgar:` so the process is stopped afterwards."""
    return MCPStdioTool(name="edgar", command="uv", args=["run", "python", "-m", "finsight.mcp_edgar"], load_prompts=False)


def edgar_http(url: str = "http://127.0.0.1:8000/mcp") -> MCPStreamableHTTPTool:
    """The same server, already running on its own (`python -m finsight.mcp_edgar --http`)."""
    return MCPStreamableHTTPTool(name="edgar", url=url, load_prompts=False)


def build_analyst(
    *extra_tools, prompt: str = "analyst", search_mode: Mode = SEARCH_MODE, page_format: str = PAGE_FORMAT,
    memory: EpisodeStore | None = None,
) -> Agent:
    """prompt: a file name in prompts/ without .md; search_mode: see D25. Both let eval configs swap one thing.
    memory: an episode store to inject past Q→A for the same company (D29); None = no episodic memory."""
    return Agent(
        client=get_client(),
        name="analyst",
        instructions=(_PROMPTS / f"{prompt}.md").read_text(),
        tools=[make_search_filings(search_mode, page_format), render_page, calculator, *extra_tools],
        default_options=AGENT_DEFAULTS,
        context_providers=[EpisodicMemory(memory)] if memory is not None else None,
    )


async def ask(agent: Agent, doc_name: str, question: str, reasoning: str | None = None) -> AgentResponse:
    """Run one question. response.value is the typed Answer.
    reasoning: an effort level ("low", "medium", ...); None keeps the model's default, which is none (D31).
    Defence B (D30): if it cites pages no tool returned this run, retry once in the same
    session. The caller can still see a failure with unread_citations()."""
    session = agent.create_session()  # so the retry sees the first attempt
    options = {"response_format": Answer} | ({"reasoning": {"effort": reasoning}} if reasoning else {})
    response = await agent.run(f"Filing: {doc_name}\n\nQuestion: {question}", session=session, options=options)
    if unread := unread_citations(response.value.citations, response):
        retry = await agent.run(
            f"You cited page(s) {unread} without reading them in this run. Memory is not evidence. "
            "Search the filing, then answer again, citing only pages you read.",
            session=session, options=options,
        )
        # One response for both attempts, so evals count every tool call and token.
        retry.messages[:0] = response.messages
        retry.usage_details = add_usage_details(response.usage_details, retry.usage_details)
        response = retry
    return response


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
