"""Research as 3 parallel analysts + a plain-code vote (Week 3, lesson w3_step3, D37).

Yes/no questions: majority of the first word. Numeric questions: the answer with the median value.
Anything else: the first analyst's answer. No LLM in the aggregator.
"""

from pathlib import Path
from statistics import median

from agent_framework import Agent
from agent_framework.orchestrations import ConcurrentBuilder
from pydantic import ValidationError

from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.models import Answer
from finsight.orchestration.handoff import combine, no_answer
from finsight.tools.calculator import calculator
from finsight.tools.filings import render_page
from finsight.tools.search_filings import make_search_filings

_PROMPTS = Path(__file__).parents[1] / "prompts"
N = 3


def pick(answers: list[Answer]) -> Answer:
    """The aggregator's rule. Pure function, so it is unit-testable offline."""
    firsts = [a.answer.split()[0].strip(".,—-").lower() if a.answer.split() else "" for a in answers]
    for word in ("yes", "no"):
        if firsts.count(word) > len(answers) / 2:
            return next(a for a, f in zip(answers, firsts) if f == word)
    valued = sorted((a for a in answers if a.value is not None), key=lambda a: a.value)
    if len(valued) > len(answers) / 2:
        return valued[len(valued) // 2]  # median: one outlier can't win
    return answers[0]


def build_concurrent(*extra_tools):
    prompt = (_PROMPTS / "analyst.md").read_text()
    agents = [Agent(client=get_client(), name=f"analyst_{i}", instructions=prompt,
                    tools=[make_search_filings(), render_page, calculator, *extra_tools],
                    default_options=AGENT_DEFAULTS | {"response_format": Answer}) for i in range(N)]
    return ConcurrentBuilder(participants=agents).with_aggregator(lambda results: results).build()


async def ask_concurrent(workflow, doc_name: str, question: str):
    result = await workflow.run(f"Filing: {doc_name}\n\nQuestion: {question}")
    results = result.get_outputs()[-1]  # list[AgentExecutorResponse]; the aggregator passes them through
    responses = [r.agent_response for r in results]
    answers = []
    for r in responses:
        try:
            answers.append(Answer.model_validate_json(r.text))
        except ValidationError:
            pass
    if not answers:
        return no_answer(), combine(responses), "failed"
    return pick(answers), combine(responses), f"{len(answers)} voted"
