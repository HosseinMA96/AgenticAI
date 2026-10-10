"""Offline tests for split building. Hand-built FinanceBench rows, no downloads."""

from finsight.dataset import COMPANIES, TEST_COMPANIES, to_record


def row(answer: str, pages: list[int]) -> dict:
    return {
        "financebench_id": "x", "company": "3M", "doc_name": "3M_2018_10K", "question": "q?",
        "answer": answer, "question_type": "metrics-generated",
        "evidence": [{"evidence_page_num": p, "evidence_text": "t"} for p in pages],
    }


def test_pages_become_one_based():
    # FinanceBench says 59 for what is PDF page 60 (checked by hand on 3M_2018_10K).
    assert to_record(row("$1577.00", [59, 59, 3]))["evidence_pages"] == [4, 60]


def test_answer_type():
    assert to_record(row("$1577.00", [0]))["answer_type"] == "numeric"
    assert to_record(row("Yes, margins improved.", [0]))["answer_type"] == "text"


def test_test_companies_are_ours_and_leave_dev_nonempty():
    assert TEST_COMPANIES < COMPANIES
