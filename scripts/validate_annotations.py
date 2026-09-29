"""Validate manual annotations of real documents.

For every ``annotations/real/*.json``: parse with the schema, and if the source
PDF is present locally, check that every quote occurs on its page.

    uv run python scripts/validate_annotations.py [files...]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from src.evaluation.annotations import (  # noqa: E402
    ANNOTATIONS_DIR,
    check_quotes,
    load_annotation,
    page_texts,
    source_path,
)


def validate(path: Path) -> int:
    print(f"== {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    try:
        ann = load_annotation(path)
    except ValidationError as e:
        print(f"  SCHEMA ERROR\n{e}")
        return 1
    print(f"  document {ann.document_id}: {len(ann.findings)} findings, status={ann.status}")
    levels = Counter(f.level.value for f in ann.findings)
    conf = Counter(f.confidence for f in ann.findings)
    print("  by level:      " + ", ".join(f"{k}={v}" for k, v in sorted(levels.items())))
    print("  by confidence: " + ", ".join(f"{k}={v}" for k, v in sorted(conf.items())))
    pdf = source_path(ann)
    if not pdf.exists():
        print(f"  quotes: SKIPPED (source {ann.source_file} not present)")
        return 0
    texts = page_texts(pdf)
    if len(texts) != ann.pages:
        print(f"  ERROR: pdf has {len(texts)} pages, annotation says {ann.pages}")
        return 1
    problems = check_quotes(ann, texts)
    total = sum(len(f.refs) for f in ann.findings)
    print(f"  quotes: {total - len(problems)}/{total} found on their page")
    for p in problems:
        print(f"    {p.finding} p.{p.page}: {p.problem}: {p.quote!r}")
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*", type=Path)
    args = ap.parse_args()
    files = args.files or sorted(ANNOTATIONS_DIR.glob("*.json"))
    if not files:
        print(f"no annotations in {ANNOTATIONS_DIR}")
        return 1
    errors = sum(validate(f.resolve()) for f in files)
    print(f"\n{len(files)} file(s), {errors} with errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
