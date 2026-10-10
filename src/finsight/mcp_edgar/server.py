"""edgar-mcp server. Tools here run in a separate process from the agent (book 12.2).

SEC rules: every request needs a descriptive User-Agent, max 10 requests/second.
"""

import asyncio
import os
import time
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# src/finsight/mcp_edgar/server.py -> parents[4] is "Stack of Agents", where the shared .env lives.
load_dotenv(Path(__file__).resolve().parents[4] / ".env")

mcp = FastMCP("edgar-mcp")

_MIN_GAP = 0.11  # seconds between requests: stays under SEC's 10/second
_last_call = 0.0
_lock = asyncio.Lock()


async def _get(url: str) -> dict:
    global _last_call
    async with _lock:  # one request at a time, spaced out
        wait = _MIN_GAP - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.monotonic()
    async with httpx.AsyncClient(headers={"User-Agent": os.environ["SEC_USER_AGENT"]}, timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def _cik(ticker: str) -> str:
    """Ticker -> 10-digit CIK, the id EDGAR uses for a company."""
    for row in (await _get("https://www.sec.gov/files/company_tickers.json")).values():
        if row["ticker"].upper() == ticker.upper():
            return f"{row['cik_str']:010d}"
    raise ValueError(f"unknown ticker {ticker!r}")


@mcp.tool()
async def list_filings(ticker: str, form: str = "10-K", limit: int = 10) -> list[dict]:
    """List a company's most recent SEC filings of one form type (e.g. '10-K', '10-Q').
    Use a stock ticker such as 'ADBE'. Returns form, filing date, period covered and accession number."""
    recent = (await _get(f"https://data.sec.gov/submissions/CIK{await _cik(ticker)}.json"))["filings"]["recent"]
    rows = [
        {"form": f, "filed": d, "period": p, "accession": a}
        for f, d, p, a in zip(recent["form"], recent["filingDate"], recent["reportDate"], recent["accessionNumber"])
        if f == form
    ]
    return rows[:limit]


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


_facts_cache: dict[str, dict] = {}  # companyfacts is several MB per company: fetch once per server run


@mcp.tool()
async def get_company_facts(ticker: str, concept: str) -> list[dict] | dict:
    """Official annual numbers a company reported to the SEC (from its 10-K XBRL data).
    `concept` is a US-GAAP name such as 'Revenues', 'NetIncomeLoss', 'Assets', 'OperatingIncomeLoss'.
    If the name isn't exact, returns matching concept names to choose from instead.
    Values are in raw units (e.g. USD, not millions)."""
    cik = await _cik(ticker)
    if cik not in _facts_cache:
        _facts_cache[cik] = (await _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"))["facts"].get("us-gaap", {})
    facts = _facts_cache[cik]

    if concept not in facts:
        # Help the agent find the right name instead of failing: XBRL names are hard to guess.
        key = concept.lower()
        matches = [name for name, f in facts.items() if key in name.lower() or key in (f.get("label") or "").lower()]
        return {"error": f"no concept {concept!r}", "did_you_mean": matches[:15]}

    rows = {}
    for unit, values in facts[concept]["units"].items():
        for v in values:
            # Keep full-year figures from 10-Ks only. A 10-K also reports its quarters, so check the
            # period is about a year long. Later filings repeat old years; keep the latest restatement.
            if v.get("form") == "10-K" and "start" in v and _days(v["start"], v["end"]) > 350:
                rows[v["end"]] = {"period_end": v["end"], "value": v["val"], "unit": unit, "filed": v["filed"]}
    return sorted(rows.values(), key=lambda r: r["period_end"], reverse=True)[:10]
