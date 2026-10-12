"""search_filings: the analyst's search over the Azure AI Search page index (D24).

Replaces the week-1 keyword tool. Same output format and the same 3 pages per
call, so the eval compares search quality, not how much text the agent reads.
"""

from typing import Annotated, Literal

from agent_framework import Content, FunctionTool, tool
from pydantic import Field

from finsight.config import PAGE_FORMAT, SEARCH_MODE, SEARCH_TOP
from finsight.rag.ingest import index_name
from finsight.rag.search import Mode, search
from finsight.tools.filings import page_png

INDEX = index_name("page")  # the winning chunker (D23)


def make_search_filings(
    mode: Mode = SEARCH_MODE, page_format: Literal["text", "image"] = PAGE_FORMAT
) -> FunctionTool:
    """A factory, so an eval can try another search mode (D25) or page format (D26) without editing config."""

    async def search_filings(
        doc_name: Annotated[str, Field(description="Filing id, e.g. 'ADOBE_2022_10K'.")],
        query: Annotated[str, Field(description="What to look for, in the words a 10-K would use, e.g. 'consolidated statements of cash flows net cash provided by operating activities'.")],
    ) -> str | list[Content]:
        """Search inside one 10-K, by meaning and by keywords. Returns the full text of the 3 best-matching pages, each headed by its page number.
        Search again with different wording if the pages don't contain what you need."""
        docs = await search(INDEX, query, doc_name, mode, top=SEARCH_TOP)
        if not docs:
            return "No pages found. Check the filing id, or try other wording."
        if page_format == "image":
            # The page number stays as text so the agent can still cite it.
            return [c for d in docs for c in (
                Content.from_text(f"[page {d['main_page']}]"),
                Content.from_data(page_png(doc_name, d["main_page"]), "image/png"),
            )]
        return "\n\n".join(f"[page {d['main_page']}]\n{d['text']}" for d in docs)

    return tool(search_filings)
