"""Research as a handoff (D36): a quick agent (no reasoning) hands off to a deep agent (reasoning on)
when a question needs math or judgement. The model picks the path, where the Router workflow lets code pick.

Both agents get the analyst's prompt and tools, so the only differences from the Router workflow are who
decides (model vs code) and the one routing paragraph in prompts/handoff_quick.md.
"""

from pathlib import Path
from types import SimpleNamespace

from agent_framework import Agent, add_usage_details
from agent_framework.orchestrations import HandoffBuilder
from pydantic import ValidationError

from finsight.config import ANALYSIS_REASONING
from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.models import Answer
from finsight.tools.calculator import calculator
from finsight.tools.filings import render_page
from finsight.tools.search_filings import make_search_filings

_PROMPTS = Path(__file__).parents[1] / "prompts"


def build_handoff(*extra_tools):
    analyst = (_PROMPTS / "analyst.md").read_text()
    common = dict(
        tools=[make_search_filings(), render_page, calculator, *extra_tools],
        # Required by HandoffBuilder (MAF 1.20): history is saved after every model call, so the
        # conversation the deep agent receives is complete even when quick stops mid tool loop.
        require_per_service_call_history_persistence=True,
    )
    quick = Agent(client=get_client(), name="quick", instructions=analyst + (_PROMPTS / "handoff_quick.md").read_text(),
                  description="Finds stated facts in the filing.",
                  default_options=AGENT_DEFAULTS | {"response_format": Answer}, **common)
    # deep's description becomes the handoff tool's description: it's what quick reads when deciding.
    deep = Agent(client=get_client(), name="deep", instructions=analyst,
                 description="Careful analyst for questions that need a calculation, a comparison or a judgement.",
                 default_options=AGENT_DEFAULTS | {"response_format": Answer, "reasoning": {"effort": ANALYSIS_REASONING}},
                 **common)
    # One way only, so they can't ping-pong (lesson w3_step2 --break).
    return HandoffBuilder(participants=[quick, deep]).with_start_agent(quick).add_handoff(quick, [deep]).build()


def combine(outputs) -> SimpleNamespace:
    """Many per-agent AgentResponses → one response-like object (all messages, summed usage) for the step meter."""
    usage = None
    for o in outputs:
        usage = add_usage_details(usage, o.usage_details) if usage else o.usage_details
    return SimpleNamespace(messages=[m for o in outputs for m in o.messages], usage_details=usage or {})


def no_answer() -> Answer:
    return Answer(reasoning="The agents ended without a valid answer.", found=False,
                  answer="No answer was produced.", value=None, unit=None, citations=[], confidence="low")


async def ask_handoff(workflow, doc_name: str, question: str):
    """Run one question. Returns (Answer, a response-like object with all messages and usage, who answered).
    If the run ends without a valid Answer (the silent failure in lesson w3_step2), returns found=False,
    so the Verifier rejects it instead of it passing as an answer."""
    result = await workflow.run(f"Filing: {doc_name}\n\nQuestion: {question}")
    outputs = result.get_outputs()  # one AgentResponse per agent turn
    combined = combine(outputs)
    who = "→".join(o.messages[-1].author_name or "?" for o in outputs if o.messages)
    try:
        answer = Answer.model_validate_json(outputs[-1].text)
    except (ValidationError, IndexError):
        answer = no_answer()
    return answer, combined, who
