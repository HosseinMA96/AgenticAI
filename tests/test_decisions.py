"""The decision log (D42): a review request is answered once, whichever checkpoint the answer comes from."""

import pytest

from finsight.orchestration.decisions import AlreadyDecided, check, record
from finsight.orchestration.messages import ReviewDecision


def test_first_answer_is_recorded(tmp_path):
    record(tmp_path, "req-1", ReviewDecision(approved=True, note="ok"))
    assert (tmp_path / "req-1.json").exists()


def test_second_answer_is_refused_and_the_first_one_kept(tmp_path):
    # Lesson w3_step12's break: `resume y` then `resume-old n` on the same request.
    record(tmp_path, "req-1", ReviewDecision(approved=True))
    with pytest.raises(AlreadyDecided) as e:
        record(tmp_path, "req-1", ReviewDecision(approved=False))
    assert e.value.first["approved"] is True


def test_different_requests_dont_block_each_other(tmp_path):
    record(tmp_path, "req-1", ReviewDecision(approved=True))
    record(tmp_path, "req-2", ReviewDecision(approved=False))


def test_check_refuses_before_the_reviewer_is_asked(tmp_path):
    check(tmp_path, "req-1")  # nothing decided yet: passes
    record(tmp_path, "req-1", ReviewDecision(approved=True))
    with pytest.raises(AlreadyDecided):
        check(tmp_path, "req-1")
