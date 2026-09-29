"""Run rule-based checks v0 on annotated real documents and compare with ground truth.

For every annotation whose source PDF is present locally. Results go to
``build/real/<doc_id>/evaluation.json`` (git-ignored: it quotes the document).

With one or a few documents these numbers are a sanity check of the pipeline,
not a quality metric.

    uv run python scripts/evaluate_real.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.crossvalidation.rules import run_rules  # noqa: E402
from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path  # noqa: E402
from src.evaluation.match import map_objects, match  # noqa: E402
from src.ingestion.real import load_pages  # noqa: E402


def pct(x: float | None) -> str:
    return "—" if x is None else f"{x:.0%}"


def main() -> int:
    anns = [load_annotation(p) for p in sorted(ANNOTATIONS_DIR.glob("*.json"))]
    anns = [a for a in anns if source_path(a).exists()]
    if not anns:
        print("no annotated real documents present locally")
        return 1
    for ann in anns:
        report = run_rules(load_pages(source_path(ann)))
        omap = map_objects(report.objects, ann.objects)
        res = match(ann.findings, report.findings, omap)
        print(f"== {ann.document_id}  (1 document: a sanity check, NOT a quality metric)")
        print("objects: " + ", ".join(f"{p} '{report.objects[p]}' -> {g}" for p, g in omap.items()))
        print(f"predicted {len(report.findings)}, ground truth {len(ann.findings)}: "
              f"precision {pct(res.precision)}, recall {pct(res.recall)}")
        print(f"\n{'level':<12} {'found':>5} {'missed':>6} {'false':>5}")
        for lvl, c in res.by_level().items():
            print(f"{lvl:<12} {c['found']:>5} {c['missed']:>6} {c['false']:>5}")
        print()
        for g, p in res.pairs:
            print(f"  found   {g.id:<4} {g.type:<28} {g.object:<8} <- {p.id}")
        for g in res.missed:
            print(f"  missed  {g.id:<4} {g.type:<28} {g.object:<8} ({g.level}, {g.confidence})")
        for p in res.false:
            print(f"  false   {p.id:<4} {p.type:<28} {omap.get(p.object, p.object):<8} {p.note}")
        if report.unresolved:
            print(f"\nunresolved object ({len(report.unresolved)}):")
            for u in report.unresolved:
                print(f"  p.{u['page']} {u['rule']}: {u['reason']}")
        out = ROOT / "build" / "real" / ann.document_id
        out.mkdir(parents=True, exist_ok=True)
        (out / "evaluation.json").write_text(json.dumps({
            "document_id": ann.document_id, "note": "single document: sanity check, not a quality metric",
            "object_map": omap, "precision": res.precision, "recall": res.recall, "by_level": res.by_level(),
            "found": [[g.id, p.id] for g, p in res.pairs], "missed": [g.id for g in res.missed],
            "false": [p.model_dump(mode="json") for p in res.false],
            "predicted": [p.model_dump(mode="json") for p in report.findings],
            "unresolved": report.unresolved,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
