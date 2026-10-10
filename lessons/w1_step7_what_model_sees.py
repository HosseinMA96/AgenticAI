"""Week 1 · Step 7 📘: what the model actually sees. The schema IS the prompt for the output (book 4.5, 15.3)."""

import asyncio
import json

from agent_framework import Agent
from pydantic import BaseModel, Field

from finsight.llm import get_client


class Bare(BaseModel):
    value: float
    unit: str


# Same fields, but now each one tells the model what we mean.
class Described(BaseModel):
    value: float = Field(description="The number only, in millions of USD. No scaling words.")
    unit: str = Field(description="Always exactly 'USD millions'.")


QUESTION = (
    "From this excerpt: 'Total net revenue for fiscal 2022 was $18.9 billion, "
    "up from $16.4 billion in 2021.' What was fiscal 2022 revenue?"
)

agent = Agent(client=get_client(), name="analyst", instructions="You are a concise financial analyst.")


async def ask(model: type[BaseModel], runs: int = 3) -> None:
    print(f"\n=== {model.__name__}: schema sent to the model ===")
    print(json.dumps(model.model_json_schema(), indent=2))
    replies = await asyncio.gather(
        *(agent.run(QUESTION, options={"response_format": model}) for _ in range(runs))
    )
    for r in replies:
        print("  ->", r.value)


async def main() -> None:
    await ask(Bare)
    await ask(Described)


asyncio.run(main())
