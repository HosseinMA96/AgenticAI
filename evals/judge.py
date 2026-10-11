"""LLM judges (D14). Week 5 checks them against the user's own labels before we trust them further."""

from pathlib import Path

from agent_framework import Agent
from pydantic import BaseModel, Field

from finsight.config import CHEAP_MODEL, MAIN_MODEL
from finsight.llm import get_client

_PROMPTS = Path(__file__).parents[1] / "src" / "finsight" / "prompts"


class Verdict(BaseModel):
    reason: str = Field(description="One sentence: why.")  # first, so it reasons before deciding
    correct: bool


def _judge(model: str, prompt_file: str) -> Agent:
    return Agent(client=get_client(model), name=prompt_file, instructions=(_PROMPTS / prompt_file).read_text())


answer_judge = _judge(MAIN_MODEL, "judge_answer.md")
citation_judge = _judge(CHEAP_MODEL, "judge_citation.md")  # only runs when the strict page check missed


async def judge_answer(question: str, gold: str, candidate: str) -> tuple[Verdict, dict]:
    r = await answer_judge.run(
        f"Question: {question}\n\nGold answer: {gold}\n\nCandidate answer: {candidate}",
        options={"response_format": Verdict},
    )
    return r.value, r.usage_details or {}


async def judge_citation(answer: str, pages: dict[int, str]) -> tuple[Verdict, dict]:
    text = "\n\n".join(f"[page {n}]\n{t}" for n, t in pages.items())
    r = await citation_judge.run(f"Answer: {answer}\n\nCited pages:\n{text}", options={"response_format": Verdict})
    return r.value, r.usage_details or {}
