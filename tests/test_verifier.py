"""Offline checks of what the Verifier is shown (D32). No model calls."""

import pytest

from finsight.agents import verifier
from finsight.models import Answer, Verdict


@pytest.fixture
def fake_pages(monkeypatch):
    # Three fake pages instead of a real PDF, so the test needs no data/.
    monkeypatch.setattr(verifier, "load_pages", lambda doc: ["p1 text", "p2 revenue 100", "p3 text"])


def answer(**kw) -> Answer:
    base = dict(reasoning="p2 is pre-restatement, trust memory", found=True, answer="Revenue was 100.",
                value=100.0, unit="USD millions", citations=[2], confidence="high")
    return Answer(**base | kw)


def test_shows_cited_pages_from_the_filing(fake_pages):
    text = verifier.verifier_input("X_2022_10K", "Revenue?", answer())
    assert "[page 2]\np2 revenue 100" in text
    assert "p1 text" not in text and "p3 text" not in text  # only what was cited


def test_hides_the_analysts_reasoning(fake_pages):
    # A poisoned excuse lives in reasoning; the Verifier must never see it (D30).
    assert "pre-restatement" not in verifier.verifier_input("X_2022_10K", "Revenue?", answer())


def test_shows_value_and_unit(fake_pages):
    assert "Value: 100.0 USD millions" in verifier.verifier_input("X_2022_10K", "Revenue?", answer())


def test_skips_pages_outside_the_filing(fake_pages):
    text = verifier.verifier_input("X_2022_10K", "Revenue?", answer(citations=[2, 99]))
    assert "[page 99]" not in text


def test_verdict_shape():
    assert Verdict(check="ok", supported=True, problem=None).supported
