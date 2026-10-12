"""Week 2, Step 2 (lesson): one table page sent as text vs as an image (book Ch 14).

Same page, same question, two ways. Compare the answers and the input tokens.

Run: uv run python lessons/w2_step2_page_image.py [PAGE] ["<question>"]
"""

import asyncio
import sys

from agent_framework import Agent, Content, Message

from finsight.llm import get_client
from finsight.tools.filings import load_pages, page_png

DOC = "ADOBE_2015_10K"
PAGE = int(sys.argv[1]) if len(sys.argv) > 1 else 63  # cash flow statement: 3 year columns
# The middle column on purpose: the one most easily confused in flattened text.
QUESTION = sys.argv[2] if len(sys.argv) > 2 else "What was stock-based compensation in fiscal 2014? Answer with the number only."

agent = Agent(client=get_client(), name="reader", instructions="Answer only from the page you are given.")


async def ask(label: str, page_content: Content) -> None:
    msg = Message(role="user", contents=[Content.from_text(QUESTION), page_content])
    response = await agent.run(msg)
    usage = response.usage_details or {}
    print(f"{label:6s} answer={response.text!r:30s} input tokens={usage.get('input_token_count')}")


async def main() -> None:
    print(f"{DOC} page {PAGE}: {QUESTION}\n")
    await ask("text", Content.from_text(load_pages(DOC)[PAGE - 1]))
    await ask("image", Content.from_data(page_png(DOC, PAGE), "image/png"))


asyncio.run(main())
