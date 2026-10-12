"""Offline tests for search_filings. Azure search is replaced by a stub."""

import asyncio

from finsight.tools import search_filings as sf


def test_formats_pages_and_passes_mode(monkeypatch):
    calls = []

    async def fake_search(index, query, filing_id, mode, top):
        calls.append((index, filing_id, mode, top))
        return [{"main_page": 63, "text": "CASH FLOWS"}, {"main_page": 59, "text": "BALANCE SHEETS"}]

    monkeypatch.setattr(sf, "search", fake_search)
    tool = sf.make_search_filings("vector")
    out = asyncio.run(tool.func("ADOBE_2015_10K", "cash flows"))
    assert out == "[page 63]\nCASH FLOWS\n\n[page 59]\nBALANCE SHEETS"
    assert calls == [("finsight-page", "ADOBE_2015_10K", "vector", 3)]


def test_no_results_tells_agent_what_to_do(monkeypatch):
    async def empty(*args, **kwargs):
        return []

    monkeypatch.setattr(sf, "search", empty)
    out = asyncio.run(sf.make_search_filings().func("NOPE_10K", "anything"))
    assert out.startswith("No pages found")


def test_image_format_keeps_page_number_as_text(monkeypatch):
    async def one_page(*args, **kwargs):
        return [{"main_page": 63, "text": "ignored"}]

    monkeypatch.setattr(sf, "search", one_page)
    monkeypatch.setattr(sf, "page_png", lambda doc, page: b"PNG")
    out = asyncio.run(sf.make_search_filings("vector", "image").func("X", "q"))
    assert [c.type for c in out] == ["text", "data"]
    assert out[0].text == "[page 63]"
