"""Offline tests for filing search. Fake pages instead of PDFs."""

import pytest

from finsight.tools import filings

FAKE = [
    "Item 1. Business overview of the company.",
    "Consolidated balance sheets. Total current liabilities 1,234.",
    "Risk factors. The company faces competition.",
]


@pytest.fixture(autouse=True)
def fake_pdf(monkeypatch):
    monkeypatch.setattr(filings, "load_pages", lambda doc: FAKE)


def test_best_page_first_and_one_based():
    assert filings.search_pages("X", "total current liabilities")[0] == 2


def test_no_match_returns_nothing():
    assert filings.search_pages("X", "goodwill impairment") == []


def test_tool_output_has_page_headers():
    out = filings.search_filing_text.func("X", "balance sheets")
    assert out.startswith("[page 2]")
