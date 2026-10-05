"""RQ2: bookkeeping for the synthetic-to-real gap: miss causes labelled by hand and the scenario choice."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

MISS_CAUSES = ("table_format", "object_resolution", "terminology", "language", "ocr", "no_rule", "other")
SCENARIO_A_MIN_DOCS = 5


def choose_scenario(n_real_annotations: int) -> str:
    """A: quantitative RQ2 (>= 5 documents); B: qualitative case analysis."""
    return "A" if n_real_annotations >= SCENARIO_A_MIN_DOCS else "B"


def load_misses(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    for fid, entry in data.items():
        if entry.get("cause") not in MISS_CAUSES:
            raise ValueError(f"{fid}: unknown cause {entry.get('cause')!r}, allowed: {MISS_CAUSES}")
    return data


def summarize_misses(missed_ids: list[str], misses: dict[str, dict]) -> dict[str, int]:
    counts = Counter(misses[i]["cause"] if i in misses else "unlabeled" for i in missed_ids)
    return dict(counts)
