"""Embed chunks, with a local cache so we never pay for the same vector twice (D18).

The cache is one JSONL file per chunker in data/embeddings/ (gitignored),
appended batch by batch, so a crashed 35-minute run resumes where it stopped.
"""

import asyncio
import json
import os
from pathlib import Path

from agent_framework.openai import OpenAIEmbeddingClient
from dotenv import load_dotenv

from finsight.dataset import DATA
from finsight.llm import _ROOT_ENV
from finsight.rag.chunkers import Chunk

EMBED_MODEL = "text-embedding-3-large"
DIMENSIONS = 1024  # D19: fits the Free tier; first dims carry most meaning
BATCH = 16  # ~16k tokens per call, well under the per-request limit
CACHE = DATA / "embeddings"


def _client() -> OpenAIEmbeddingClient:
    load_dotenv(_ROOT_ENV)
    return OpenAIEmbeddingClient(
        model=EMBED_MODEL,
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )


def load_cache(name: str) -> dict[str, list[float]]:
    path = CACHE / f"{name}.jsonl"
    if not path.exists():
        return {}
    return {row["id"]: row["vector"] for row in map(json.loads, path.open())}


async def embed_chunks(name: str, chunks: list[Chunk]) -> dict[str, list[float]]:
    """Return {chunk id: vector}, calling the API only for chunks not in the cache."""
    vectors = load_cache(name)
    todo = [c for c in chunks if c.id not in vectors]
    print(f"{name}: {len(vectors)} cached, {len(todo)} to embed")
    if not todo:
        return vectors

    client = _client()
    CACHE.mkdir(parents=True, exist_ok=True)
    tokens = 0
    with (CACHE / f"{name}.jsonl").open("a") as out:
        for i in range(0, len(todo), BATCH):
            batch = todo[i : i + BATCH]
            for attempt in range(6):
                try:
                    result = await client.get_embeddings(
                        [c.text for c in batch], options={"dimensions": DIMENSIONS}
                    )
                    break
                except Exception as e:  # mostly 429: our quota is 120K tokens/minute
                    if attempt == 5:
                        raise
                    print(f"  retry in 20s ({type(e).__name__})")
                    await asyncio.sleep(20)
            tokens += (result.usage or {}).get("input_token_count", 0)
            for c, e in zip(batch, result):
                vectors[c.id] = e.vector
                out.write(json.dumps({"id": c.id, "vector": e.vector}) + "\n")
            out.flush()  # so a crash keeps everything embedded so far
            if i // BATCH % 20 == 0:
                print(f"  {i + len(batch)}/{len(todo)} chunks, {tokens:,} tokens")
    print(f"  done: {tokens:,} tokens embedded")
    return vectors
