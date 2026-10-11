"""Deterministic scoring: no model involved (D14)."""

import re

# Allowed unit mix-ups: millions vs billions vs raw, and ratio vs percent.
_SCALES = (1, 1e3, 1e-3, 1e6, 1e-6, 1e9, 1e-9, 100, 0.01)
TOLERANCE = 0.01  # 1% relative: covers gold answers rounded to 2 decimals


def parse_number(text: str) -> float | None:
    """'$1,577.00' -> 1577.0, '(3.5)' -> -3.5, '17.98' -> 17.98."""
    m = re.search(r"\(?-?\$?\s*[\d,]*\.?\d+", text)
    if not m:
        return None
    s = m.group()
    neg = s.startswith("(") or "-" in s
    value = float(re.sub(r"[^\d.]", "", s))
    return -value if neg else value


def numbers_match(gold: float, got: float | None) -> bool:
    if got is None:
        return False
    if gold == 0:
        return abs(got) < 1e-9
    return any(abs(got * k - gold) <= TOLERANCE * abs(gold) for k in _SCALES)


def citation_hit(cited: list[int], gold_pages: list[int]) -> bool:
    return bool(set(cited) & set(gold_pages))


# Retrieval metrics (D21). `retrieved` is the page list of each result, best first:
# one page per page chunk, possibly several per fixed-size chunk.
def hit_at_k(retrieved: list[list[int]], gold_pages: list[int], k: int) -> float:
    """1.0 if any gold page is among the top k results."""
    found = {p for pages in retrieved[:k] for p in pages}
    return float(bool(found & set(gold_pages)))


def recall_at_k(retrieved: list[list[int]], gold_pages: list[int], k: int) -> float:
    """Fraction of gold pages among the top k results."""
    found = {p for pages in retrieved[:k] for p in pages}
    return len(found & set(gold_pages)) / len(set(gold_pages))
