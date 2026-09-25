"""Generate bilingual synthetic document sets.

Examples:
    uv run python scripts/generate_synthetic.py --lang ru kz --seeds 1 --inject all \
        --out data/synthetic/samples
    uv run python scripts/generate_synthetic.py --lang ru kz --seeds 1-200   # random injections
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ner.common.taxonomy import DiscrepancyType  # noqa: E402
from src.synthesis.generator import LANGS, generate_set  # noqa: E402


def parse_seeds(spec: str) -> list[int]:
    seeds: list[int] = []
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        seeds.extend(range(int(lo), int(hi or lo) + 1))
    return seeds


def parse_inject(spec: str) -> set[DiscrepancyType] | None:
    if spec == "random":
        return None
    if spec == "all":
        return set(DiscrepancyType)
    if spec == "none":
        return set()
    return {DiscrepancyType(s.strip()) for s in spec.split(",")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", nargs="+", choices=LANGS, default=list(LANGS))
    ap.add_argument("--seeds", default="1", help="e.g. '1', '1-50', '3,7,10-12'")
    ap.add_argument("--inject", default="random",
                    help="random | all | none | comma list of " + ", ".join(t.value for t in DiscrepancyType))
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "synthetic")
    ap.add_argument("--no-scans", action="store_true", help="skip the (slower) scan rendering")
    args = ap.parse_args()

    inject = parse_inject(args.inject)
    for lang in args.lang:
        for seed in parse_seeds(args.seeds):
            set_dir = generate_set(lang, seed, args.out, inject, scans=not args.no_scans)
            gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
            kinds = ", ".join(f"{d['id']}:{d['type']}" for d in gt["discrepancies"]) or "none"
            print(f"{set_dir.relative_to(ROOT) if set_dir.is_relative_to(ROOT) else set_dir}  "
                  f"[{gt['object']['object_name']}]  discrepancies: {kinds}")


if __name__ == "__main__":
    main()
