"""End-to-end evaluation of the rule-based MVP against synthetic ground truth.

Detection: a GT discrepancy is found if the report has a non-MATCH finding of
the same type on the same field; any other non-MATCH finding is a false positive.
Extraction: exact value match per GT field the extractor targets.

    uv run python scripts/eval_pipeline.py data/synthetic/eval --kind text/*.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import analyze_package  # noqa: E402

TARGET_PREFIXES = ("floors", "building_area", "total_area", "construction_volume", "underground", "estimated_cost",
                   "construction_duration", "explication_total", "room.", "concrete_", "rebar", "brick", "steel",
                   "local_qty.", "os.total", "ssr.ch2", "ssr.total", "local.total")


def key(dtype: str, field: str) -> tuple[str, str]:
    if dtype == "COST_OBJECT_ESTIMATE_VS_SUMMARY":
        return dtype, "cost"
    if dtype == "AREA_PZ_VS_AR_EXPLICATION":
        return dtype, "area"
    return dtype, field.removeprefix("local_qty.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+", type=Path)
    ap.add_argument("--kind", default="text/*.pdf", help="glob inside a set: text/*.pdf | text/*.docx | scan/*.pdf")
    args = ap.parse_args()

    det: dict[tuple[str, str], Counter] = defaultdict(Counter)  # (lang, type) -> tp/fp/fn
    ext: dict[str, Counter] = defaultdict(Counter)
    errors = Counter()
    for gt_path in sorted(p for r in args.roots for p in r.rglob("ground_truth.json")):
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        lang = gt["lang"]
        report = analyze_package(sorted(gt_path.parent.glob(args.kind)))
        want = {key(d["type"], d["field"]) for d in gt["discrepancies"]}
        got = {key(f["type"], f["field"]) for f in report["findings"] if f["verdict"] != "MATCH"}
        for k in want | got:
            det[(lang, k[0])]["tp" if k in want and k in got else ("fn" if k in want else "fp")] += 1
            if k not in want or k not in got:
                errors[(lang, "FN" if k in want else "FP", k[0], k[1])] += 1
        det[(lang, "_sets")]["n"] += 1
        for sec, fields in gt["tep"].items():
            got_sec = report["tep"].get(sec, {})
            for fld, e in fields.items():
                if not e["present"] or not fld.startswith(TARGET_PREFIXES):
                    continue
                c = ext[lang]
                c["total"] += 1
                if fld in got_sec:
                    c["correct" if abs(got_sec[fld]["value"] - e["value"]) < 1e-6 else "wrong"] += 1

    print(f"== {args.kind}")
    for lang in sorted({k[0] for k in det}):
        print(f"[{lang}] sets: {det[(lang, '_sets')]['n']}")
        c = ext[lang]
        print(f"  extraction: {c['correct']}/{c['total']} correct = {c['correct'] / max(c['total'], 1):.1%}"
              f"  (wrong value: {c['wrong']}, not found: {c['total'] - c['correct'] - c['wrong']})")
        for (lg, t), cnt in sorted(det.items()):
            if lg != lang or t == "_sets":
                continue
            p = cnt["tp"] / max(cnt["tp"] + cnt["fp"], 1)
            r = cnt["tp"] / max(cnt["tp"] + cnt["fn"], 1)
            print(f"  {t:38} TP={cnt['tp']:3} FP={cnt['fp']:3} FN={cnt['fn']:3}  P={p:6.1%}  R={r:6.1%}")
    if errors:
        print("  most common errors:", errors.most_common(8))


if __name__ == "__main__":
    main()
