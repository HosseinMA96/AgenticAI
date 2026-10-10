"""Week 1 · Step 8 📘: when typing goes wrong. A required field forces the model to fill it, even with a guess (book 4.5, 11.3)."""

import asyncio

from agent_framework import Agent
from pydantic import BaseModel, Field, ValidationInfo, model_validator

from finsight.llm import get_client


# --- Break it: every field required, so the model MUST produce a number. ---
class Answer(BaseModel):
    value: float = Field(description="The number, in millions of USD.")
    citations: list[int] = Field(description="Page numbers that support the value.")


# --- Fix it: give the model an honest way out, then check what it cites. ---
class Defended(BaseModel):
    # Defense 1: None is a legal answer, and the description says when to use it.
    value: float | None = Field(
        description="The number in millions of USD, for the exact period asked. "
        "null if the excerpt does not state it."
    )
    # Defense 2: say exactly what counts as a citation.
    citations: list[int] = Field(
        description="Only page numbers from [page N] tags whose text states the value. Empty if value is null."
    )

    # Defense 3: a validator the model can't talk its way past. It runs in OUR code.
    @model_validator(mode="after")
    def check_citations(self, info: ValidationInfo) -> "Defended":
        if self.value is not None and not self.citations:
            raise ValueError("a value needs at least one citation")
        if self.value is None and self.citations:
            raise ValueError("no value, so there should be no citations")
        known = (info.context or {}).get("pages")
        if known is not None and not set(self.citations) <= known:
            raise ValueError(f"cites pages {set(self.citations) - known} that weren't in the evidence")
        return self


EXCERPT = (
    "[page 41] Total net revenue for fiscal 2022 was $18,902.1 million, "
    "up from $16,384.0 million in 2021."
)
PAGES_GIVEN = {41}

agent = Agent(client=get_client(), name="analyst", instructions="You are a concise financial analyst.")


async def ask(model: type[BaseModel], year: int, runs: int = 3) -> None:
    question = f"Excerpt:\n{EXCERPT}\n\nWhat was fiscal {year} revenue?"
    replies = await asyncio.gather(
        *(agent.run(question, options={"response_format": model}) for _ in range(runs))
    )
    print(f"\n=== {model.__name__}, asking for {year} ===")
    for r in replies:
        # MAF validated the shape; we re-validate with context so Defense 3 sees the real page list.
        checked = model.model_validate(r.value.model_dump(), context={"pages": PAGES_GIVEN})
        print("  ->", checked)


async def main() -> None:
    await ask(Answer, 2023)  # not in the excerpt: watch it guess
    await ask(Defended, 2023)  # not in the excerpt: should say null
    await ask(Defended, 2022, runs=1)  # control: still answers when it CAN


asyncio.run(main())
