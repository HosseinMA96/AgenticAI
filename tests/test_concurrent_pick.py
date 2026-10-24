"""The Concurrent vote is plain code, so it is tested offline (D37)."""

from finsight.models import Answer
from finsight.orchestration.concurrent import pick


def mk(text: str, value: float | None = None) -> Answer:
    return Answer(reasoning="r", found=True, answer=text, value=value, unit="u" if value is not None else None,
                  citations=[1], confidence="low")


def test_yes_no_majority():
    assert pick([mk("Yes."), mk("No"), mk("yes, it is")]).answer == "Yes."


def test_numeric_median_beats_outlier():
    assert pick([mk("a", 1), mk("b", 9), mk("c", 2)]).answer == "c"


def test_no_agreement_takes_first():
    assert pick([mk("x"), mk("y"), mk("z")]).answer == "x"
