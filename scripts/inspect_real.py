"""Dump a real PDF for manual inspection and measure TEP extractability.

Writes to ``build/real/<doc_id>/`` (git-ignored, the content is client data):
``pages/NNN.txt`` (raw page text), ``tables.json`` (tables with repaired
headers and bboxes) and, if an annotation with this ``source_file`` exists,
``extractability.json``.

    uv run python scripts/inspect_real.py "data/real/<file>.pdf"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation  # noqa: E402
from src.evaluation.extractability import measure, to_json  # noqa: E402
from src.ingestion.real import load_pages  # noqa: E402


def find_annotation(pdf: Path):
    for path in sorted(ANNOTATIONS_DIR.glob("*.json")):
        ann = load_annotation(path)
        if (ROOT / ann.source_file).resolve() == pdf.resolve():
            return ann
    return None


def slug(name: str) -> str:
    return re.sub(r"[^\w]+", "_", name, flags=re.UNICODE).strip("_").lower()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "real")
    args = ap.parse_args()
    if not args.pdf.exists():
        print(f"not found: {args.pdf}")
        return 1

    ann = find_annotation(args.pdf)
    doc_id = ann.document_id if ann else slug(args.pdf.stem)
    out = args.out / doc_id
    (out / "pages").mkdir(parents=True, exist_ok=True)

    pages = load_pages(args.pdf)
    for p in pages:
        (out / "pages" / f"{p.number:03d}.txt").write_text(p.text, encoding="utf-8")
    tables = [{"page": p.number, "index": i, **asdict(t)} for p in pages for i, t in enumerate(p.tables)]
    (out / "tables.json").write_text(json.dumps(tables, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{doc_id}: {len(pages)} pages, {len(tables)} tables -> {out}")

    if ann is None:
        print("no annotation for this file: extractability not measured")
        return 0
    hits = measure(ann, pages)
    report = to_json(hits)
    (out / "extractability.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'object':<6} {'field':<24} {'expected':>10}  {'where':<6} {'col':<4} pages")
    for h in hits:
        pages_s = f"table {h.table_pages} text {h.text_pages}"
        flags = " trivial" if h.trivial else ""
        flags += " ambiguous" if h.ambiguous else ""
        print(f"{h.object:<6} {h.field:<24} {h.expected:>10g}  {h.where:<6} {'yes' if h.column_ok else 'no':<4} "
              f"{pages_s}{flags}")
    print("\nsummary:", json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
