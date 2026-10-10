"""Week 1 · Step 6 📘: free text vs typed. Same question, two ways (book 4.5)."""

import asyncio
import re

from agent_framework import Agent
from pydantic import BaseModel

from finsight.llm import get_client


class Answer(BaseModel):
    value: float
    unit: str


QUESTION = (
    "From this excerpt: 'Total net revenue for fiscal 2022 was $18,902.1 million, "
    "up from $16,384.0 million in 2021.' What was fiscal 2022 revenue?"
)

agent = Agent(client=get_client(), name="analyst", instructions="You are a concise financial analyst.")


async def main() -> None:
    # 1. Free text: we get a sentence and have to dig the number out ourselves.
    free = await agent.run(QUESTION)
    print("free text:", repr(free.text))
    match = re.search(r"[\d,]+\.?\d*", free.text)  # fragile: grabs the FIRST number it sees
    print("  regex parse ->", match.group() if match else None)

    # 2. Typed: MAF sends Answer's JSON schema to the API, and the reply is parsed into Answer.
    typed = await agent.run(QUESTION, options={"response_format": Answer})
    print("\ntyped raw text:", typed.text)
    print("  response.value ->", repr(typed.value))
    print("  value * 2 =", typed.value.value * 2)  # a real float, ready for math


asyncio.run(main())
