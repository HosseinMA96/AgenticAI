"""Offline tests for the Answer model. Hand-built dicts, no model."""

import pytest
from pydantic import ValidationError

from finsight.models import Answer

NUMERIC = {
    "reasoning": "Stated on page 41.",
    "found": True,
    "answer": "Fiscal 2022 revenue was $18,902.1 million.",
    "value": 18902.1,
    "unit": "USD millions",
    "citations": [41],
    "confidence": "high",
}
WRITTEN = NUMERIC | {"answer": "Yes, one customer accounted for 16% of revenue.", "value": None, "unit": None}
NOT_FOUND = {
    "reasoning": "2023 is not in the excerpt.",
    "found": False,
    "answer": "The excerpt has no fiscal 2023 revenue.",
    "value": None,
    "unit": None,
    "citations": [],
    "confidence": "low",
}


@pytest.mark.parametrize("data", [NUMERIC, WRITTEN, NOT_FOUND])
def test_legal_answers(data):
    Answer.model_validate(data)


@pytest.mark.parametrize(
    "base, change",
    [
        (NUMERIC, {"citations": []}),  # found without citation
        (WRITTEN, {"citations": []}),  # same for a written answer
        (NUMERIC, {"unit": None}),  # value without unit
        (NUMERIC, {"citations": [0]}),  # impossible page
        (NUMERIC, {"confidence": "very high"}),  # not one of the three levels (D7)
        (NOT_FOUND, {"citations": [41]}),  # not found, yet cites a page
        (NOT_FOUND, {"value": 1.0, "unit": "USD millions"}),  # not found, yet has a number
    ],
)
def test_rejects_bad_answer(base, change):
    with pytest.raises(ValidationError):
        Answer.model_validate(base | change)


def test_rejects_page_not_in_evidence():
    with pytest.raises(ValidationError, match=r"\[99\]"):
        Answer.model_validate(NUMERIC | {"citations": [41, 99]}, context={"pages": {41, 42}})


def test_page_check_skipped_without_context():
    assert Answer.model_validate(NUMERIC | {"citations": [99]}).citations == [99]
