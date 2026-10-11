"""Build one search index: chunk all filings, embed, upload to Azure AI Search.

Run: uv run python -m finsight.rag.ingest page|fixed
One chunker's index at a time, to fit the Free tier's 50 MB (D18).
"""

import asyncio
import os
import sys

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType as T,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    SearchableField,
    VectorSearch,
    VectorSearchProfile,
)
from dotenv import load_dotenv

from finsight.dataset import PDFS
from finsight.llm import _ROOT_ENV
from finsight.rag.chunkers import fixed_chunks, page_chunks
from finsight.rag.embed import DIMENSIONS, embed_chunks
from finsight.tools.filings import load_pages

CHUNKERS = {"page": page_chunks, "fixed": fixed_chunks}
UPLOAD_BATCH = 100  # a 1024-float vector is ~20 KB as JSON; keeps requests well under 16 MB


def index_name(chunker: str) -> str:
    return f"finsight-{chunker}"


def index_schema(name: str) -> SearchIndex:
    return SearchIndex(
        name=name,
        fields=[
            SimpleField(name="id", type=T.STRING, key=True),
            # Filterable, so a search can be limited to one filing.
            SimpleField(name="filing_id", type=T.STRING, filterable=True),
            SimpleField(name="pages", type="Collection(Edm.Int32)", filterable=True),
            SimpleField(name="main_page", type=T.INT32, filterable=True),
            # Searchable = goes into the keyword (BM25) half of hybrid search.
            SearchableField(name="text"),
            # The vector half. Not returned in results: nobody needs to read 1024 floats.
            SearchField(
                name="vector",
                type="Collection(Edm.Single)",
                searchable=True,
                retrievable=False,
                vector_search_dimensions=DIMENSIONS,
                vector_search_profile_name="hnsw",
            ),
        ],
        # HNSW: an approximate nearest-neighbour graph, fast instead of comparing every vector.
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw-algo")],
            profiles=[VectorSearchProfile(name="hnsw", algorithm_configuration_name="hnsw-algo")],
        ),
        # What the semantic reranker reads when it re-scores the top results.
        semantic_search=SemanticSearch(
            default_configuration_name="default",
            configurations=[
                SemanticConfiguration(
                    name="default",
                    prioritized_fields=SemanticPrioritizedFields(
                        content_fields=[SemanticField(field_name="text")]
                    ),
                )
            ],
        ),
    )


def index_client() -> SearchIndexClient:
    load_dotenv(_ROOT_ENV)
    return SearchIndexClient(
        os.environ["AZURE_SEARCH_ENDPOINT"], AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"])
    )


async def main(chunker: str) -> None:
    chunk = CHUNKERS[chunker]
    chunks = [c for pdf in sorted(PDFS.glob("*.pdf")) for c in chunk(pdf.stem, load_pages(pdf.stem))]
    print(f"{chunker}: {len(chunks)} chunks from {len(list(PDFS.glob('*.pdf')))} filings")

    vectors = await embed_chunks(chunker, chunks)

    name = index_name(chunker)
    async with index_client() as indexes:
        await indexes.create_or_update_index(index_schema(name))
        async with indexes.get_search_client(name) as search:
            for i in range(0, len(chunks), UPLOAD_BATCH):
                docs = [c.model_dump() | {"vector": vectors[c.id]} for c in chunks[i : i + UPLOAD_BATCH]]
                results = await search.upload_documents(documents=docs)
                failed = [r.key for r in results if not r.succeeded]
                if failed:
                    raise RuntimeError(f"upload failed for {failed[:5]}")
            print(f"uploaded {len(chunks)} documents to {name}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
