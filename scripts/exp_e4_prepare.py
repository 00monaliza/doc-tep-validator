"""E4: prepare the synthetic package for commercial tools and a template for manual observations.

    uv run python scripts/exp_e4_prepare.py --out build/research/e4
Give only ``<set>/text/*.pdf`` to a tool (synthetic data only); ``expected.json`` stays with you.
Fill ``observations.csv`` by hand while running Armeta / Norma.AI on a free trial (see docs/research/e4-protocol.md).
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.protocol import E4_SEEDS, seed_list  # noqa: E402
from src.synthesis.generator import generate_set  # noqa: E402

SEEDS = seed_list(E4_SEEDS)
TOOLS = ("Armeta", "Norma.AI")
COLUMNS = ["set", "tool", "found_types", "false_alarms", "evidence_given", "language_ok", "notes"]


def prepare(out: Path, langs=("ru", "kz")) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    dirs, rows = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for lang in langs:
            for seed in SEEDS:
                src = generate_set(lang, seed, Path(tmp), scans=False, profile="v2")
                dst = out / f"{lang}_{seed}"
                (dst / "text").mkdir(parents=True, exist_ok=True)
                for pdf in sorted(src.glob("text/*.pdf")):
                    shutil.copy(pdf, dst / "text" / pdf.name)
                gt = json.loads((src / "ground_truth.json").read_text(encoding="utf-8"))
                expected = [{"id": d["id"], "type": d["type"], "field": d["field"], "object": d.get("object", "")}
                            for d in gt["discrepancies"]]
                (dst / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
                dirs.append(dst)
                rows += [{"set": dst.name, "tool": t} for t in TOOLS]
    with (out / "observations.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows({c: r.get(c, "") for c in COLUMNS} for r in rows)
    return dirs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "research" / "e4")
    args = ap.parse_args()
    dirs = prepare(args.out)
    print(f"prepared {len(dirs)} sets in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
