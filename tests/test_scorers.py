"""Offline tests for the deterministic eval scorers."""

import pytest

from evals.scorers import citation_hit, hit_at_k, numbers_match, parse_number, recall_at_k


@pytest.mark.parametrize("text, expected", [("$1577.00", 1577.0), ("17.98", 17.98), ("$(3.5)", -3.5), ("-12%", -12.0), ("none", None)])
def test_parse_number(text, expected):
    assert parse_number(text) == expected


@pytest.mark.parametrize(
    "gold, got, ok",
    [
        (1616.0, 1615.9, True),  # rounding
        (1577.0, 1.577, True),  # agent answered in billions
        (0.66, 66.0, True),  # ratio vs percent
        (12645.0, 12000.0, False),  # genuinely off
        (17.98, None, False),  # no value given
    ],
)
def test_numbers_match(gold, got, ok):
    assert numbers_match(gold, got) is ok


def test_citation_hit():
    assert citation_hit([85, 52], [52]) and not citation_hit([85], [52])


def test_summary_and_leaderboard_cells_with_one_answer_type():
    # Regression: a --limit run with no written questions crashed when formatting the leaderboard row.
    from evals.run import _pct, summarize

    row = {"correct": True, "answer_type": "numeric", "latency_s": 1.0, "usage": {}, "citation_hit": True,
           "citation_supported": True, "cost_usd": 0.0, "tool_calls": 1}
    s = summarize([row])
    assert (_pct(s["accuracy_numeric"]), _pct(s["accuracy_text"])) == ("100%", "–")


def test_retry_on_rate_limit_only(monkeypatch):
    import asyncio

    import httpx
    import openai

    from evals import run

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(run.asyncio, "sleep", no_wait)
    req = httpx.Request("POST", "https://x")
    limit = openai.RateLimitError("429", response=httpx.Response(429, request=req), body=None)
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("wrapped") from limit  # how MAF wraps it
        return "ok"

    assert asyncio.run(run.with_retry(flaky)) == "ok" and len(calls) == 3

    async def broken():
        raise ValueError("real bug")

    import pytest
    with pytest.raises(ValueError):
        asyncio.run(run.with_retry(broken))  # other errors are not retried


def test_retrieval_metrics_with_two_gold_pages():
    retrieved = [[40], [63], [51], [59]]  # gold 63 at rank 2, gold 59 at rank 4
    gold = [59, 63]
    assert hit_at_k(retrieved, gold, 1) == 0.0
    assert hit_at_k(retrieved, gold, 3) == 1.0
    assert recall_at_k(retrieved, gold, 3) == 0.5  # only half the evidence
    assert recall_at_k(retrieved, gold, 5) == 1.0


def test_multi_page_chunk_counts_all_its_pages():
    assert recall_at_k([[62, 63]], [63], 1) == 1.0  # rule A; D22 decides fairness for fixed-size
