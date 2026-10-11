"""Query an index built by rag.ingest, in one of four modes (book 4.8).

The modes exist so the retrieval eval can measure what each part adds.
The agent's tool will use one of them (TODO: search_filings).
"""

from typing import Literal

from azure.search.documents.models import VectorizedQuery

from finsight.rag.embed import DIMENSIONS, _client
from finsight.rag.ingest import index_client

Mode = Literal["keyword", "vector", "hybrid", "hybrid+rerank"]
MODES: tuple[Mode, ...] = ("keyword", "vector", "hybrid", "hybrid+rerank")
VECTOR_CANDIDATES = 50  # nearest neighbours fed into fusion; the reranker re-reads the top 50 too


async def embed_query(text: str) -> list[float]:
    result = await _client().get_embeddings([text], options={"dimensions": DIMENSIONS})
    return result[0].vector


async def search(
    index: str,
    query: str,
    filing_id: str,
    mode: Mode,
    top: int = 5,
    vector: list[float] | None = None,  # pass a precomputed query vector to avoid re-embedding
) -> list[dict]:
    """Return the top chunks as dicts with id, pages, main_page and text, best first."""
    kwargs: dict = {"filter": f"filing_id eq '{filing_id}'", "top": top, "select": ["id", "pages", "main_page", "text"]}
    if mode != "keyword":
        vector = vector or await embed_query(query)
        kwargs["vector_queries"] = [
            VectorizedQuery(vector=vector, k_nearest_neighbors=VECTOR_CANDIDATES, fields="vector")
        ]
    if mode == "hybrid+rerank":
        kwargs["query_type"] = "semantic"  # uses the index's default semantic configuration
    # search_text=None turns off the keyword half, leaving pure vector search.
    search_text = None if mode == "vector" else query

    async with index_client() as indexes, indexes.get_search_client(index) as client:
        results = await client.search(search_text, **kwargs)
        return [doc async for doc in results]
