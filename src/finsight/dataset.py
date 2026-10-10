"""FinanceBench data: pick our questions (D8) and download their PDFs.

Run: uv run python -m finsight.dataset
Everything lands in data/ (gitignored). Safe to re-run: existing files are skipped.
"""

import json
import urllib.request
from pathlib import Path

# src/finsight/dataset.py -> parents[2] is FinalProject/.
DATA = Path(__file__).resolve().parents[2] / "data"
RAW = DATA / "raw"
PDFS = DATA / "pdfs"

_REPO = "https://raw.githubusercontent.com/patronus-ai/financebench/main"

# The 12 companies with the most 10-K questions (D8).
COMPANIES = {
    "AMD", "Boeing", "American Express", "PepsiCo", "3M", "Adobe",
    "Amcor", "Best Buy", "Verizon", "Corning", "CVS Health", "General Mills",
}


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


if __name__ == "__main__":
    qs = selected_questions()
    print(f"{len(qs)} questions from {len({q['company'] for q in qs})} companies")
    download_pdfs(qs)
