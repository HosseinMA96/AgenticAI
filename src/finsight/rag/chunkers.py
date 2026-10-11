"""Two ways to cut a filing into chunks for the search index (D19).

Both take page texts (from tools.filings.load_pages) and return Chunks, so they
stay pure and testable offline. Page numbers are 1-based, as everywhere else.
"""

from collections import Counter

import tiktoken
from pydantic import BaseModel

# The tokenizer text-embedding-3-large uses, so "1024 tokens" is exact (D20).
_ENC = tiktoken.encoding_for_model("text-embedding-3-large")

CHUNK_TOKENS = 1024  # about one page (median page is 762 tokens), D19
OVERLAP_TOKENS = 128


class Chunk(BaseModel):
    id: str
    filing_id: str
    # A list because a fixed-size chunk can straddle pages (91% of them do).
    # How to score those fairly in recall@k is decided in the retrieval eval.
    pages: list[int]
    # The page holding most of the chunk's tokens: the fair page to score it by (D22).
    main_page: int
    text: str


def page_chunks(filing_id: str, pages: list[str]) -> list[Chunk]:
    """One chunk per page. No page exceeds the embedding input limit, so none is split (D20)."""
    return [
        Chunk(id=f"{filing_id}-p{n}", filing_id=filing_id, pages=[n], main_page=n, text=text)
        for n, text in enumerate(pages, start=1)
        if text.strip()  # blank pages (covers, separators) would only add noise
    ]


def fixed_chunks(
    filing_id: str, pages: list[str], size: int = CHUNK_TOKENS, overlap: int = OVERLAP_TOKENS
) -> list[Chunk]:
    """Windows of `size` tokens over the whole filing, blind to page edges."""
    # Tokenize page by page and remember which page each token came from,
    # so every window knows which pages it covers.
    tokens: list[int] = []
    page_of: list[int] = []
    for n, text in enumerate(pages, start=1):
        ids = _ENC.encode(text)
        tokens += ids
        page_of += [n] * len(ids)

    chunks = []
    for i, start in enumerate(range(0, len(tokens), size - overlap)):
        window = slice(start, start + size)
        chunks.append(
            Chunk(
                id=f"{filing_id}-c{i}",
                filing_id=filing_id,
                pages=sorted(set(page_of[window])),
                main_page=Counter(page_of[window]).most_common(1)[0][0],
                text=_ENC.decode(tokens[window]),
            )
        )
        if start + size >= len(tokens):  # this window reached the end
            break
    return chunks
