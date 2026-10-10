"""Offline tests for edgar-mcp tools. Fake SEC responses, no network."""

import asyncio

import pytest

from finsight.mcp_edgar import server

TICKERS = {"0": {"cik_str": 796343, "ticker": "ADBE"}}
FACTS = {"facts": {"us-gaap": {"Revenues": {"label": "Revenues", "units": {"USD": [
    {"start": "2019-11-30", "end": "2020-11-27", "val": 12868, "form": "10-K", "filed": "2021-01-15"},
    {"start": "2020-08-29", "end": "2020-11-27", "val": 3424, "form": "10-K", "filed": "2021-01-15"},  # a quarter
    {"start": "2019-11-30", "end": "2020-11-27", "val": 12868, "form": "10-Q", "filed": "2021-03-01"},  # not a 10-K
]}}}}}


@pytest.fixture(autouse=True)
def fake_sec(monkeypatch):
    async def fake_get(url):
        return TICKERS if "company_tickers" in url else FACTS
    monkeypatch.setattr(server, "_get", fake_get)
    server._facts_cache.clear()


def test_keeps_only_full_year_10k_values():
    rows = asyncio.run(server.get_company_facts("ADBE", "Revenues"))
    assert [r["value"] for r in rows] == [12868]


def test_unknown_concept_suggests_names():
    out = asyncio.run(server.get_company_facts("adbe", "revenue"))
    assert out["did_you_mean"] == ["Revenues"]


def test_unknown_ticker():
    with pytest.raises(ValueError):
        asyncio.run(server.get_company_facts("NOPE", "Revenues"))
