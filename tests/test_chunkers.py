"""Offline tests for the two chunkers. Fake pages instead of PDFs."""

from finsight.rag.chunkers import _ENC, fixed_chunks, page_chunks


def test_page_chunks_one_per_page_and_skip_blank():
    chunks = page_chunks("X", ["first page", "   \n", "third page"])
    assert [c.pages for c in chunks] == [[1], [3]]  # 1-based, blank page 2 dropped
    assert chunks[1].id == "X-p3"


def test_fixed_chunks_size_overlap_and_coverage():
    pages = [" ".join(f"word{i}" for i in range(300))] * 4  # several hundred tokens per page
    chunks = fixed_chunks("X", pages, size=200, overlap=50)
    sizes = [len(_ENC.encode(c.text)) for c in chunks]
    assert max(sizes) <= 201  # decode/re-encode can shift a token at the edge
    # Consecutive windows share their edge text (the overlap).
    assert chunks[0].text[-40:] in chunks[1].text
    # Every page is covered by some chunk, and the last chunk reaches the last page.
    assert set().union(*(c.pages for c in chunks)) == {1, 2, 3, 4}
    assert chunks[-1].pages[-1] == 4


def test_fixed_chunk_can_straddle_pages():
    chunks = fixed_chunks("X", ["short page one", "short page two"], size=1024)
    assert len(chunks) == 1 and chunks[0].pages == [1, 2]
