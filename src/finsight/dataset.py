"""FinanceBench data: pick our questions (D8), download their PDFs, write dev/test splits (D9).

Run: uv run python -m finsight.dataset
Everything lands in data/ (gitignored). Safe to re-run: existing files are skipped.
"""

import json
import re
import urllib.request
from pathlib import Path

# src/finsight/dataset.py -> parents[2] is FinalProject/.
DATA = Path(__file__).resolve().parents[2] / "data"
RAW = DATA / "raw"
PDFS = DATA / "pdfs"
SPLITS = DATA / "splits"

_REPO = "https://raw.githubusercontent.com/patronus-ai/financebench/main"

# The 12 companies with the most 10-K questions (D8).
COMPANIES = {
    "AMD", "Boeing", "American Express", "PepsiCo", "3M", "Adobe",
    "Amcor", "Best Buy", "Verizon", "Corning", "CVS Health", "General Mills",
}
# Held out by company, so tuning on dev never touches a test filing (D9).
# Picked for balance (24 questions, 8 numeric) and so each test sector also appears in dev.
TEST_COMPANIES = {"3M", "AMD", "Best Buy", "PepsiCo"}

_NUMERIC = re.compile(r"^\s*[-$(]*\s*[\d,]+(\.\d+)?\s*%?\)?\s*(million|billion|x|times)?\s*\.?$", re.I)


def _fetch(url: str, dest: Path) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")  # no half-written files if interrupted
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def selected_questions() -> list[dict]:
    """Our questions: 10-K filings of the D8 companies."""
    _fetch(f"{_REPO}/data/financebench_open_source.jsonl", RAW / "financebench_open_source.jsonl")
    _fetch(f"{_REPO}/data/financebench_document_information.jsonl", RAW / "financebench_document_information.jsonl")
    doc_type = {d["doc_name"]: d["doc_type"] for d in _read_jsonl(RAW / "financebench_document_information.jsonl")}
    return [
        q for q in _read_jsonl(RAW / "financebench_open_source.jsonl")
        if q["company"] in COMPANIES and doc_type[q["doc_name"]] == "10k"
    ]


def download_pdfs(questions: list[dict]) -> None:
    docs = sorted({q["doc_name"] for q in questions})
    for i, doc in enumerate(docs, 1):
        dest = PDFS / f"{doc}.pdf"
        print(f"[{i}/{len(docs)}] {doc}", "(cached)" if dest.exists() else "")
        _fetch(f"{_REPO}/pdfs/{doc}.pdf", dest)


def to_record(q: dict) -> dict:
    """One FinanceBench row -> our slimmer split row."""
    return {
        "id": q["financebench_id"],
        "company": q["company"],
        "doc_name": q["doc_name"],
        "question": q["question"],
        "answer": q["answer"],
        "answer_type": "numeric" if _NUMERIC.match(q["answer"]) else "text",
        "question_type": q["question_type"],
        # FinanceBench pages are 0-based; PDF viewers and our citations are 1-based.
        "evidence_pages": sorted({e["evidence_page_num"] + 1 for e in q["evidence"]}),
        "evidence_texts": [e["evidence_text"] for e in q["evidence"]],
    }


def make_splits(questions: list[dict]) -> None:
    SPLITS.mkdir(parents=True, exist_ok=True)
    for name, keep in [("dev", lambda c: c not in TEST_COMPANIES), ("test", lambda c: c in TEST_COMPANIES)]:
        rows = [to_record(q) for q in questions if keep(q["company"])]
        with open(SPLITS / f"{name}.jsonl", "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
        n_num = sum(r["answer_type"] == "numeric" for r in rows)
        print(f"{name}: {len(rows)} questions ({n_num} numeric), {len({r['company'] for r in rows})} companies")


if __name__ == "__main__":
    qs = selected_questions()
    print(f"{len(qs)} questions from {len({q['company'] for q in qs})} companies")
    download_pdfs(qs)
    make_splits(qs)
