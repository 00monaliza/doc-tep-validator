"""Find where a quoted value sits on a PDF page (for highlighting in the viewer).

The page-text extractors (``ingestion.real``, ``tep_baseline``, rules v0) keep a
page number and a quote, not coordinates. This module searches the quote on the
page and narrows it to the value text inside it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from src.ingestion.common.layout import BBox
from src.ingestion.common.numbers import NUMBER_RE, number_readings


def raw_number(quote: str, value: float) -> str | None:
    """The number token of `quote` that reads as `value` (the last one if several do)."""
    hits = [m.group(0) for m in NUMBER_RE.finditer(quote)
            if any(abs(r - value) < 1e-6 for r in number_readings(m.group(0)))]
    return hits[-1].strip() if hits else None


def _union(boxes: list[dict]) -> BBox:
    return (min(b["x0"] for b in boxes), min(b["top"] for b in boxes),
            max(b["x1"] for b in boxes), max(b["bottom"] for b in boxes))


def _flexible(text: str) -> str:
    """Regex for `text` that tolerates any whitespace (line breaks, cell borders) between its words."""
    return r"\s*".join(re.escape(w) for w in text.split())


class Locator:
    """Caches open PDFs; `bbox()` returns the value's box, else the quote's, else None."""

    def __init__(self) -> None:
        self._pdfs: dict[str, pdfplumber.PDF] = {}

    def _page(self, path: Path, page_no: int):
        key = str(path)
        if key not in self._pdfs:
            self._pdfs[key] = pdfplumber.open(path)
        pages = self._pdfs[key].pages
        return pages[page_no - 1] if 1 <= page_no <= len(pages) else None

    def bbox(self, path: Path, page_no: int, quote: str, raw: str | None = None) -> BBox | None:
        page = self._page(path, page_no)
        if page is None or not quote:
            return None
        hits = page.search(_flexible(quote), regex=True)
        if not hits and len(quote) > 40:  # long quotes may be broken by table layout: try the head
            hits = page.search(_flexible(quote[:40]), regex=True)
        if raw:
            values = page.search(_flexible(raw), regex=True)
            if hits:  # the value inside (or nearest to) the quote
                q = _union(hits[:1])
                inside = sorted((b for b in values if b["top"] >= q[1] - 2 and b["bottom"] <= q[3] + 2),
                                key=lambda b: (round(b["top"]), b["x0"]))
                # a row may repeat the number ("ИТОГО … 113,28 113,28"): take the occurrence
                # with the same index as in the quote (the extractors read the last one)
                k = len(re.findall(rf"(?<![\d,.]){re.escape(raw)}(?![\d])", quote)) - 1
                if inside:
                    return _union([inside[min(max(k, 0), len(inside) - 1)]])
                values = sorted(values, key=lambda b: abs(b["top"] - q[1]) + abs(b["x0"] - q[0]) / 4)
            if values:
                return _union(values[:1])
        return _union(hits[:1]) if hits else None

    def close(self) -> None:
        for pdf in self._pdfs.values():
            pdf.close()
        self._pdfs.clear()
