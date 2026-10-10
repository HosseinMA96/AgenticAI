"""Read 10-K filings: page text plus a keyword search tool (D10, D11).

Page numbers are 1-based everywhere, matching the PDF viewer and dataset.py.
"""

import math
import re
from collections import Counter
from functools import cache
from typing import Annotated

import pymupdf
from agent_framework import tool
from pydantic import Field

from finsight.dataset import PDFS

_WORD = re.compile(r"[a-z0-9]+")
# Words too common to help find a page.
_STOP = {"the", "a", "an", "of", "and", "or", "in", "on", "for", "to", "is", "was", "what", "how", "by", "as", "at", "its", "fy"}


def _words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP]


@cache  # parse each PDF once per process
def load_pages(doc_name: str) -> list[str]:
    with pymupdf.open(PDFS / f"{doc_name}.pdf") as pdf:
        return [page.get_text() for page in pdf]


def search_pages(doc_name: str, query: str, k: int = 3) -> list[int]:
    """Plain TF-IDF ranking: pages that use the query's rarer words most rank first."""
    pages = [Counter(_words(p)) for p in load_pages(doc_name)]
    terms = set(_words(query))
    df = {t: sum(t in p for p in pages) for t in terms}  # pages containing each term
    idf = {t: math.log(len(pages) / df[t]) for t in terms if df[t]}  # rare words count more

    def score(p: Counter) -> float:
        return sum(math.log1p(p[t]) * idf[t] for t in idf)

    ranked = sorted(range(len(pages)), key=lambda i: score(pages[i]), reverse=True)
    return [i + 1 for i in ranked[:k] if score(pages[i]) > 0]


@tool
def search_filing_text(
    doc_name: Annotated[str, Field(description="Filing id, e.g. 'ADOBE_2022_10K'.")],
    query: Annotated[str, Field(description="Keywords as they would appear in a 10-K, e.g. 'consolidated balance sheets total current liabilities'.")],
) -> str:
    """Keyword search inside one 10-K. Returns the full text of the 3 best-matching pages, each headed by its page number.
    Search again with different keywords if the pages don't contain what you need."""
    hits = search_pages(doc_name, query)
    if not hits:
        return "No pages matched. Try other keywords."
    pages = load_pages(doc_name)
    return "\n\n".join(f"[page {n}]\n{pages[n - 1]}" for n in hits)
