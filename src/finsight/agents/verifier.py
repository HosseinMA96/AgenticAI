"""The Verifier: checks one Answer against the pages it cites, in a clean context (D32)."""

from pathlib import Path

from agent_framework import Agent, AgentResponse

from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.models import Answer, Verdict
from finsight.tools.calculator import calculator
from finsight.tools.filings import load_pages

_PROMPTS = Path(__file__).parents[1] / "prompts"


def build_verifier() -> Agent:
    return Agent(
        client=get_client(),
        name="verifier",
        instructions=(_PROMPTS / "verifier.md").read_text(),
        tools=[calculator],  # no search: it judges the cited pages only, it doesn't do research again (D32)
        # The default effort here is none (D31). Checking arithmetic needs some thinking.
        default_options=AGENT_DEFAULTS | {"response_format": Verdict, "reasoning": {"effort": "low"}},
    )


def verifier_input(doc_name: str, question: str, answer: Answer) -> str:
    """What the Verifier sees. Pages come from the PDF via our code, not from the analyst's
    messages, and answer.reasoning is left out, so a poisoned excuse can't get in (D30, D32)."""
    pages = load_pages(doc_name)
    cited = "\n\n".join(f"[page {n}]\n{pages[n - 1]}" for n in sorted(set(answer.citations)) if 1 <= n <= len(pages))
    claim = answer.answer + (f"\nValue: {answer.value} {answer.unit or ''}".rstrip() if answer.value is not None else "")
    return f"Filing: {doc_name}\n\nQuestion: {question}\n\nAnswer: {claim}\n\nCited pages:\n\n{cited}"


async def verify(verifier: Agent, doc_name: str, question: str, answer: Answer) -> AgentResponse:
    """response.value is the typed Verdict. Assumes answer.citations is non-empty;
    the workflow decides what to do with "not found" answers before calling this."""
    return await verifier.run(verifier_input(doc_name, question, answer))
