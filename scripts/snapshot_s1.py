"""Slots of S1 on a few final seeds, to pin S1 to the frozen protocol (run on the protocol-v1 tag).

    uv run python scripts/snapshot_s1.py OUT.json
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.systems import RulesSystem  # noqa: E402
from src.synthesis.generator import generate_set  # noqa: E402

SEEDS = (8000, 8001, 8002)

if __name__ == "__main__":
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for lang in ("ru", "kz"):
            for seed in SEEDS:
                d = generate_set(lang, seed, Path(tmp), scans=False, profile="v2")
                slots = RulesSystem().detect(sorted((d / "text").glob("*.pdf")), lang)
                out[f"{lang}_{seed}"] = sorted(list(s) for s in slots)
    Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
