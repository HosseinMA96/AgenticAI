"""The Router: a cheap model that labels each question, so the workflow can pick a path (D31)."""

from pathlib import Path

from agent_framework import Agent, AgentResponse

from finsight.config import CHEAP_MODEL
from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.models import Route

_PROMPTS = Path(__file__).parents[1] / "prompts"


def build_router() -> Agent:
    # No tools: labelling needs only the question and the filing name, which keeps it fast and cheap.
    return Agent(
        client=get_client(CHEAP_MODEL),
        name="router",
        instructions=(_PROMPTS / "router.md").read_text(),
        default_options=AGENT_DEFAULTS | {"response_format": Route},
    )


async def route(router: Agent, doc_name: str, question: str) -> AgentResponse:
    """response.value is the typed Route. The whole response is returned (like analyst.ask) so evals can count tokens.
    Same input shape as the analyst, so the Router sees which filing the question is asked against."""
    return await router.run(f"Filing: {doc_name}\n\nQuestion: {question}")
