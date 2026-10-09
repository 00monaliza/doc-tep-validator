"""Rule-based TEP extraction baseline vs the one-phrase regex, on synthetic sets.

Generates the sets on the fly (text-layer ПЗ only), runs
``src/ner/common/tep_baseline.py`` and ``scripts/regex_baseline.py`` and prints
slot-level precision / recall / F1 per field, plus sentence-only extraction.
Seeds 1-20 were used while writing the rules; report on unseen seeds.

    uv run python scripts/eval_tep_extraction.py --seeds 5001-5040 --lang ru kz --profile v2
    uv run python scripts/eval_tep_extraction.py --real      # dev real document(s), if present
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.regex_baseline import regex_extract  # noqa: E402
from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path  # noqa: E402
from src.evaluation.extraction_eval import (  # noqa: E402
    FIELDS,
    Scores,
    gold_slots,
    predicted_slots,
    real_verdicts,
    text_scores,
)
from src.ingestion.common import pdf  # noqa: E402
from src.ingestion.real import load_pages  # noqa: E402
from src.ner.common.tep_baseline import STAGES, extract  # noqa: E402
from src.synthesis.generator import generate_set  # noqa: E402


def seeds(spec: str) -> list[int]:
    lo, _, hi = spec.partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


def fmt(p: float, r: float, f1: float) -> str:
    return f"{p:5.2f} {r:5.2f} {f1:5.2f}"


def run_synthetic(args) -> dict:
    report = {}
    with tempfile.TemporaryDirectory() as tmp:
        for profile in args.profile:
            for lang in args.lang:
                base, rx = Scores(), Scores()
                t_tp, t_fp, t_fn, obj_ok = Counter(), Counter(), Counter(), []
                ignored = 0
                for seed in seeds(args.seeds):
                    set_dir = generate_set(lang, seed, Path(tmp) / profile, scans=False, profile=profile)
                    gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
                    pz = set_dir / "text" / "PZ.pdf"
                    gold = gold_slots(gt)
                    ex = extract(load_pages(pz))
                    pred, ign = predicted_slots(ex, gt, gold)
                    ignored += ign
                    base.add(pred, gold)
                    rx.add({("b1", f): v for f, v in regex_extract(pdf.extract_text(pz), lang).items()}, gold)
                    tp, fp, fn, ok = text_scores(ex, gt)
                    t_tp, t_fp, t_fn = t_tp + tp, t_fp + fp, t_fn + fn
                    obj_ok += ok
                print(f"\n== {profile} {lang}, seeds {args.seeds}: slot extraction (P R F1)")
                print(f"{'field':<30} {'gold':>5}  {'rule baseline':<17}  regex (one phrase)")
                rows = {}
                for f in (*FIELDS, None):
                    b, r = base.prf(f), rx.prf(f)
                    name = f or "ALL"
                    rx_s = fmt(*r[:3]) if f in (None, "total_area_m2", "building_area_m2") else "    —"
                    print(f"{name:<30} {b[3]:>5}  {fmt(*b[:3])}  {rx_s}")
                    rows[name] = {"gold": b[3], "baseline": b[:3], "regex": r[:3]}
                print(f"(building fields outside any building in multi-building sets, not scored: {ignored})")
                tp, fp, fn = sum(t_tp.values()), sum(t_fp.values()), sum(t_fn.values())
                p = tp / (tp + fp) if tp + fp else 0
                r = tp / (tp + fn) if tp + fn else 0
                print(f"sentences only: P {p:.2f} R {r:.2f} (tp {tp}, fp {fp}, fn {fn}); "
                      f"object of matched building mentions correct: {sum(obj_ok)}/{len(obj_ok)}")
                for f in sorted(set(t_tp) | set(t_fp) | set(t_fn)):
                    print(f"   {f:<28} tp {t_tp[f]:>3} fp {t_fp[f]:>3} fn {t_fn[f]:>3}")
                report[f"{profile}_{lang}"] = rows
    return report


def run_real(stages) -> None:
    for path in sorted(ANNOTATIONS_DIR.glob("*.json")):
        ann = load_annotation(path)
        if not source_path(ann).exists():
            continue
        print(f"\n== {ann.document_id} (dev document: the lexicon may contain its labels)")
        for obj, f, value, verdict in real_verdicts(extract(load_pages(source_path(ann)), stages=stages), ann):
            print(f"  {obj:<5} {f:<30} {value:>10g}  {verdict}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", default="5001-5040")
    ap.add_argument("--lang", nargs="+", default=["ru", "kz"])
    ap.add_argument("--profile", nargs="+", default=["v2"])
    ap.add_argument("--real", action="store_true", help="evaluate on annotated real dev documents instead")
    ap.add_argument("--json", type=Path, help="write the slot scores here")
    args = ap.parse_args()
    if args.real:
        run_real(STAGES)
        return 0
    report = run_synthetic(args)
    if args.json:
        args.json.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
