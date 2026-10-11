"""S1 vs S2 on synthetic sets: P/R/F1 by discrepancy type (slots = type + field, as in E3).

    uv run python scripts/eval_detectors.py --profile v4 --seeds 1-50          # development
    uv run python scripts/eval_detectors.py --profile v4 --seeds 9000-9099     # final, once
    uv run python scripts/eval_detectors.py --profile v2 --seeds 8000-8019     # regression: no new false alarms
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

from src.evaluation.bench import gt_slots  # noqa: E402
from src.evaluation.systems import RulesSystem, RulesSystemV1  # noqa: E402
from src.synthesis.generator import PROFILES, generate_set  # noqa: E402


def seeds(spec: str) -> list[int]:
    lo, _, hi = spec.partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


def prf(tp: int, fp: int, fn: int) -> str:
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else float("nan")
    return f"{p:5.2f} {r:5.2f} {f:5.2f}  (tp {tp} fp {fp} fn {fn})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile", default="v4", choices=PROFILES)
    ap.add_argument("--seeds", default="1-50")
    ap.add_argument("--lang", nargs="+", default=["ru", "kz"])
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    systems = [RulesSystem(), RulesSystemV1()]
    report = {}
    with tempfile.TemporaryDirectory() as tmp:
        for lang in args.lang:
            counts = {s.name: (Counter(), Counter(), Counter()) for s in systems}
            for seed in seeds(args.seeds):
                d = generate_set(lang, seed, Path(tmp), scans=False, profile=args.profile)
                want = gt_slots(json.loads((d / "ground_truth.json").read_text(encoding="utf-8")))
                paths = sorted((d / "text").glob("*.pdf"))
                for s in systems:
                    got = s.detect(paths, lang)
                    tp, fp, fn = counts[s.name]
                    for k in want & got:
                        tp[k] += 1
                    for k in got - want:
                        fp[k] += 1
                    for k in want - got:
                        fn[k] += 1
            print(f"\n== {args.profile} {lang}, seeds {args.seeds}")
            keys = sorted({k for c in counts.values() for part in c for k in part})
            for s in systems:
                tp, fp, fn = counts[s.name]
                print(f"{s.name} ALL {'':<40} {prf(sum(tp.values()), sum(fp.values()), sum(fn.values()))}")
                for k in keys:
                    print(f"   {k[0]:<28} {k[1]:<22} {prf(tp[k], fp[k], fn[k])}")
                report[f"{lang}_{s.name}"] = {"|".join(k): [tp[k], fp[k], fn[k]] for k in keys}
    if args.json:
        args.json.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
