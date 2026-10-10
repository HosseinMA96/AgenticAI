"""Offline tests for the Answer model. Hand-built dicts, no model."""

import pytest
from pydantic import ValidationError

from finsight.models import Answer

GOOD = {
    "reasoning": "Stated on page 41.",
    "value": 18902.1,
    "unit": "USD millions",
    "citations": [41],
    "confidence": "high",
}
NOT_FOUND = {"reasoning": "2023 is not in the excerpt.", "value": None, "unit": None, "citations": [], "confidence": "low"}


def test_good_answer():
    assert Answer.model_validate(GOOD).value == 18902.1


def test_not_found_is_legal():
    assert Answer.model_validate(NOT_FOUND).value is None


@pytest.mark.parametrize(
    "change",
    [
        {"citations": []},  # value without citation
        {"unit": None},  # value without unit
        {"citations": [0]},  # impossible page
        {"confidence": "very high"},  # not one of the three levels (D7)
    ],
)
def test_rejects_bad_answer(change):
    with pytest.raises(ValidationError):
        Answer.model_validate(GOOD | change)


def test_rejects_citations_without_value():
    with pytest.raises(ValidationError):
        Answer.model_validate(NOT_FOUND | {"citations": [41]})


def test_rejects_page_not_in_evidence():
    with pytest.raises(ValidationError, match=r"\[99\]"):
        Answer.model_validate(GOOD | {"citations": [41, 99]}, context={"pages": {41, 42}})


def test_page_check_skipped_without_context():
    assert Answer.model_validate(GOOD | {"citations": [99]}).citations == [99]
