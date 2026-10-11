"""Building parameters (``src/ner/data/parameter_lexicon.json``): how they are mentioned and their values.

Used by ``crossvalidation.rules_v1``. Mentions and material synonyms are word prefixes; in a phrase the
longest material synonym wins ("асфальтобетонная" is asphalt, not concrete).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from src.ingestion.common.numbers import NUMBER_RE, number_readings

PARAMETERS_PATH = Path(__file__).resolve().parents[1] / "data" / "parameter_lexicon.json"
_WIDTH_RE = re.compile(rf"(?:ширин\w*|ені)\D{{0,15}}?(?P<num>{NUMBER_RE.pattern})\s*(?P<unit>мм|м)(?![^\W\d_])",
                       re.IGNORECASE)


def _words(by_lang: dict) -> list[str]:
    return list(dict.fromkeys(w.lower() for by_src in by_lang.values() for ws in by_src.values() for w in ws))


@dataclass(frozen=True, eq=False)
class Parameter:
    name: str
    mention_re: re.Pattern[str]
    materials: dict[str, list[str]]
    has_width: bool
    unit: str | None

    def material_in(self, text: str) -> str | None:
        low = text.lower().replace("ё", "е")
        best, best_len = None, 0
        for material, words in self.materials.items():
            for w in words:
                if re.search(rf"(?<![^\W\d_]){re.escape(w)}", low) and len(w) > best_len:
                    best, best_len = material, len(w)
        return best


@cache
def load_parameters(path: Path = PARAMETERS_PATH) -> dict[str, Parameter]:
    data = json.loads(path.read_text(encoding="utf-8"))["parameters"]
    out = {}
    for name, spec in data.items():
        words = _words(spec["mention"])
        alternatives = [re.escape(w).replace(r"\ ", r"\s+") for w in words]
        mention = re.compile("|".join(rf"(?<![^\W\d_]){alt}\w*" for alt in alternatives), re.IGNORECASE)
        materials = {m: _words(v) for m, v in spec.get("materials", {}).items()}
        out[name] = Parameter(name, mention, materials, bool(spec.get("width")), spec.get("unit"))
    return out


def width_mm(text: str) -> float | None:
    m = _WIDTH_RE.search(text)
    if not m or not (readings := number_readings(m.group("num"))):
        return None
    return round(readings[0] * (1000 if m.group("unit").lower() == "м" else 1), 1)
