"""Research as a group chat maker-checker (Week 3, lesson w3_step4): the analyst answers, a checker tries to
break the answer, and its issues go back to the analyst until it approves or max_rounds ends the chat.

Unlike the Verifier (one verdict after the fact), the critique reaches the maker inside the same run.
"""

from pathlib import Path

from agent_framework import Agent
from agent_framework.orchestrations import GroupChatBuilder, GroupChatState
from pydantic import BaseModel, ValidationError

from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.models import Answer
from finsight.orchestration.handoff import combine, no_answer
from finsight.tools.calculator import calculator
from finsight.tools.filings import render_page
from finsight.tools.search_filings import make_search_filings

_PROMPTS = Path(__file__).parents[1] / "prompts"
MAX_ROUNDS = 6  # maker, checker × 3: the lesson's runaway case ended exactly here


class Review(BaseModel):
    approved: bool
    issues: list[str]


def _agent(name: str, prompt: str, fmt: type[BaseModel], tools: list) -> Agent:
    return Agent(client=get_client(), name=name, instructions=prompt, tools=tools,
                 default_options=AGENT_DEFAULTS | {"response_format": fmt})


def _next_speaker(state: GroupChatState) -> str:
    return "maker" if state.current_round % 2 == 0 else "checker"


def _approved(conversation) -> bool:
    last = conversation[-1]
    if last.author_name != "checker":
        return False
    try:
        return Review.model_validate_json(last.text).approved
    except ValidationError:
        return False


def build_maker_checker(*extra_tools):
    tools = [make_search_filings(), render_page, calculator, *extra_tools]
    return GroupChatBuilder(
        participants=[_agent("maker", (_PROMPTS / "analyst.md").read_text(), Answer, tools),
                      _agent("checker", (_PROMPTS / "checker.md").read_text(), Review, tools)],
        selection_func=_next_speaker, termination_condition=_approved, max_rounds=MAX_ROUNDS,
        output_from="all",  # else the only output is the orchestrator's "terminated" line (lesson w3_step4)
    ).build()


async def ask_maker_checker(workflow, doc_name: str, question: str):
    """Returns (Answer, response-like with all usage, "maker×N" or "maker×N!" if max_rounds ended it)."""
    result = await workflow.run(f"Filing: {doc_name}\n\nQuestion: {question}")
    outputs = [e.data for e in result if e.type == "output" and hasattr(e.data, "usage_details")]
    makers = [e.data for e in result if e.type == "output" and e.executor_id == "maker"]
    checkers = [e.data for e in result if e.type == "output" and e.executor_id == "checker"]
    try:
        approved = Review.model_validate_json(checkers[-1].text).approved
        answer = Answer.model_validate_json(makers[-1].text)
    except (ValidationError, IndexError):
        return no_answer(), combine(outputs), "failed"
    return answer, combine(outputs), f"maker×{len(makers)}" + ("" if approved else "!")
