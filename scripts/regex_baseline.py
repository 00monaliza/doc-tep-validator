"""Naive regex baseline: is the synthetic corpus still trivially easy?

Looks for "<label> м² <number>" (the v1 ТЭП table row of the total area) in the
ПЗ text layer and compares it with ground truth ``tep.PZ.total_area_m2``. On
profile v1 this gives 100 %; profile v2 is meant to break it.

    uv run python scripts/regex_baseline.py --seeds 5001-5040 --profile v1 v2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion.common import pdf  # noqa: E402
from src.synthesis.formatting import parse_num  # noqa: E402
from src.synthesis.generator import generate_set  # noqa: E402

PATTERNS = {
    "ru": re.compile(r"Общая площадь здания\s+м²\s+(\d[\d  ]*,\d+)"),
    "kz": re.compile(r"Ғимараттың жалпы ауданы\s+м²\s+(\d[\d  ]*,\d+)"),
}


def seeds(spec: str) -> list[int]:
    lo, _, hi = spec.partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", default="5001-5040")
    ap.add_argument("--lang", nargs="+", default=["ru", "kz"])
    ap.add_argument("--profile", nargs="+", default=["v1", "v2"])
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        for profile in args.profile:
            for lang in args.lang:
                ok, fails = 0, {"no match": 0, "wrong value": 0}
                ss = seeds(args.seeds)
                for seed in ss:
                    set_dir = generate_set(lang, seed, Path(tmp) / profile, scans=False, profile=profile)
                    gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
                    m = PATTERNS[lang].search(pdf.extract_text(set_dir / "text" / "PZ.pdf"))
                    if m is None:
                        fails["no match"] += 1
                    elif abs(parse_num(m.group(1)) - gt["tep"]["PZ"]["total_area_m2"]["value"]) < 0.005:
                        ok += 1
                    else:
                        fails["wrong value"] += 1
                print(f"{profile} {lang}: {ok}/{len(ss)} = {ok / len(ss):.0%}   failures: {fails}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
