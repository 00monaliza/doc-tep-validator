"""E1 (RQ1): ceiling by extractability on annotated real documents.

    uv run python scripts/exp_e1_ceiling.py
Output: build/research/e1_ceiling.json and a markdown table on stdout. Documents whose PDF is absent are skipped.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path  # noqa: E402
from src.evaluation.ceiling import ceiling_table, classify_finding  # noqa: E402
from src.ingestion.real import load_pages  # noqa: E402

OUT = ROOT / "build" / "research"
CLASSES = ("table_reachable", "text_reachable", "beyond_rules")


def main() -> int:
    anns = [load_annotation(p) for p in sorted(ANNOTATIONS_DIR.glob("*.gt.json"))]
    anns = [a for a in anns if source_path(a).exists()]
    if not anns:
        print("no annotated real documents present locally")
        return 1
    all_pairs, per_doc = [], {}
    for ann in anns:
        pages = load_pages(source_path(ann))
        pairs = [(f, classify_finding(f, pages)) for f in ann.findings]
        all_pairs += pairs
        per_doc[ann.document_id] = {f.id: cls for f, cls in pairs}
    table = ceiling_table(all_pairs)
    total = len(all_pairs)
    print(f"documents: {len(anns)}, findings: {total}\n")
    print("| level | " + " | ".join(CLASSES) + " |\n|---|" + "---|" * len(CLASSES))
    for lvl, row in sorted(table.items()):
        print(f"| {lvl} | " + " | ".join(str(row.get(c, 0)) for c in CLASSES) + " |")
    reachable = sum(c != "beyond_rules" for _, c in all_pairs)
    print(f"\nreachable by number comparison: {reachable}/{total}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "e1_ceiling.json").write_text(json.dumps(
        {"documents": len(anns), "findings": total, "table": table, "per_doc": per_doc},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
