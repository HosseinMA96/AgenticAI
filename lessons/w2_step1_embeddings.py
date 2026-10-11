"""Week 2, Step 1 (lesson): embeddings find meaning, not words.

Embed one question and a few whole pages of Adobe's 2015 10-K, then rank the
pages by how close their vectors are to the question's. Book 4.8.

Run: uv run python lessons/w2_step1_embeddings.py ["<your question>"]
"""

import asyncio
import os
import re
import sys
from pathlib import Path

import pymupdf
from agent_framework.openai import OpenAIEmbeddingClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Plain words on purpose: the filing says "operating activities", not "day-to-day business".
QUESTION = sys.argv[1] if len(sys.argv) > 1 else (
    "How much cash did Adobe's day-to-day business bring in during 2015?"
)
PDF = Path("data/pdfs/ADOBE_2015_10K.pdf")
PAGES = [10, 30, 59, 63, 80]  # 1-based; 63 is the cash flow statement (gold evidence)


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


async def main() -> None:
    doc = pymupdf.open(PDF)
    texts = [doc[p - 1].get_text() for p in PAGES]  # pymupdf counts from 0

    client = OpenAIEmbeddingClient(
        model="text-embedding-3-large",
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )
    # One call embeds the question and all pages together.
    result = await client.get_embeddings([QUESTION, *texts], options={"dimensions": 1024})
    vectors = [e.vector for e in result]
    print(f"{len(vectors)} vectors of {len(vectors[0])} numbers; usage: {result.usage}\n")

    q, pages = vectors[0], vectors[1:]
    # The vectors come back with length 1, so a dot product is the cosine similarity.
    scores = [sum(a * b for a, b in zip(page, q)) for page in pages]
    q_words = words(QUESTION)
    print(f"Q: {QUESTION}\n")
    print("page  similarity  shared words  exact question text on page?")
    for i in sorted(range(len(PAGES)), key=lambda i: -scores[i]):
        exact = "yes" if QUESTION in texts[i] else ""
        print(f"{PAGES[i]:>4}  {scores[i]:>10.3f}  {len(q_words & words(texts[i])):>12}  {exact}")


asyncio.run(main())
