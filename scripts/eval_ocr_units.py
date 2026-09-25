"""Measure м²/м³ recovery on scans: raw OCR vs naive digit mapping vs context normalisation.

Reference = text layer of the same document (exact м²/м³). Each reference line
with units is aligned to its most similar OCR line; units are compared in order.

    uv run python scripts/eval_ocr_units.py data/synthetic/samples [more dirs...]
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pdfplumber
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion.common.normalize import EXP_HINT, normalize_units  # noqa: E402
from src.ingestion.common.ocr import ocr_image  # noqa: E402

REF_UNIT = re.compile(r"м[²³]")
OCR_UNIT = re.compile(r"(?<![^\W\d_])[мМm][2²3³зЗ?*]?(?![^\W_])")
MIN_LINE_SIMILARITY = 0.6


def strip_units(s: str) -> str:
    return OCR_UNIT.sub("", s)


def evaluate(set_dirs: list[Path]) -> dict[str, Counter]:
    stats: dict[str, Counter] = {}
    for set_dir in set_dirs:
        gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
        c = stats.setdefault(gt["lang"], Counter())
        for doc in gt["documents"].values():
            with pdfplumber.open(set_dir / doc["text_pdf"]) as pdf:
                ref_pages = [p.extract_text() or "" for p in pdf.pages]
            for ref_text, page_img in zip(ref_pages, doc["scan_pages"], strict=True):
                raw = ocr_image(Image.open(set_dir / page_img), gt["lang"])
                norm, _ = normalize_units(raw)
                raw_lines, norm_lines = raw.split("\n"), norm.split("\n")
                keys = [strip_units(line) for line in raw_lines]
                for ref_line in ref_text.split("\n"):
                    ref_units = REF_UNIT.findall(ref_line)
                    if not ref_units:
                        continue
                    c["ref_units"] += len(ref_units)
                    target = strip_units(ref_line)
                    scores = [difflib.SequenceMatcher(None, target, k).ratio() for k in keys]
                    best = max(range(len(keys)), key=scores.__getitem__, default=None)
                    if best is None or scores[best] < MIN_LINE_SIMILARITY:
                        c["line_not_aligned"] += len(ref_units)
                        continue
                    raw_units = OCR_UNIT.findall(raw_lines[best])
                    norm_units = OCR_UNIT.findall(norm_lines[best])
                    if len(raw_units) != len(ref_units):
                        c["unit_count_mismatch"] += len(ref_units)
                        continue
                    for ref_u, raw_u, norm_u in zip(ref_units, raw_units, norm_units, strict=True):
                        c["aligned"] += 1
                        c["raw_exact"] += raw_u == ref_u
                        c["naive_digit"] += len(raw_u) == 2 and EXP_HINT.get(raw_u[1]) == ref_u[1]
                        c["normalized"] += norm_u == ref_u
    return stats


def main() -> None:
    roots = [Path(a) for a in sys.argv[1:]] or [ROOT / "data" / "synthetic" / "samples"]
    set_dirs = sorted(p.parent for r in roots for p in r.rglob("ground_truth.json"))
    for lang, c in evaluate(set_dirs).items():
        a = c["aligned"] or 1
        print(f"[{lang}] reference units: {c['ref_units']}, aligned: {c['aligned']} "
              f"(line not found: {c['line_not_aligned']}, unit count differs: {c['unit_count_mismatch']})")
        for key, label in (("raw_exact", "raw OCR"), ("naive_digit", "naive 2→² 3/з→³"),
                           ("normalized", "context normalisation")):
            print(f"    {label:24} {c[key]:4}/{c['aligned']}  = {c[key] / a:6.1%}")


if __name__ == "__main__":
    main()
