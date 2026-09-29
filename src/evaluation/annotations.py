"""Loading annotations of real documents and checking their quotes against the PDF."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from src.evaluation.schema import RealAnnotation

ROOT = Path(__file__).resolve().parents[2]
ANNOTATIONS_DIR = ROOT / "annotations" / "real"


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def load_annotation(path: str | Path) -> RealAnnotation:
    return RealAnnotation.model_validate_json(Path(path).read_text(encoding="utf-8"))


def source_path(ann: RealAnnotation) -> Path:
    return ROOT / ann.source_file


def page_texts(pdf_path: str | Path) -> list[str]:
    """pdfplumber text of every page, whitespace-normalized; index 0 is page 1."""
    with pdfplumber.open(pdf_path) as pdf:
        return [norm_ws(p.extract_text() or "") for p in pdf.pages]


@dataclass
class QuoteProblem:
    finding: str
    page: int
    quote: str
    problem: str  # "not found" | "found on pages [..]" | "count N != M"


def check_quotes(ann: RealAnnotation, texts: list[str]) -> list[QuoteProblem]:
    problems = []
    for f in ann.findings:
        for r in f.refs:
            q = norm_ws(r.quote)
            text = texts[r.page - 1] if r.page <= len(texts) else ""
            n = text.count(q)
            if n == 0:
                elsewhere = [i + 1 for i, t in enumerate(texts) if q in t]
                problems.append(QuoteProblem(f.id, r.page, r.quote,
                                             f"found on pages {elsewhere}" if elsewhere else "not found"))
            elif r.occurrences is not None and n != r.occurrences:
                problems.append(QuoteProblem(f.id, r.page, r.quote, f"count {n} != {r.occurrences}"))
    return problems
