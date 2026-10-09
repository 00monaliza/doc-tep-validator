"""TEP lexicon (``src/ner/data/tep_lexicon.json``): field labels, units, table header words.

The only source of TEP wordings for the extractors; every entry names its source.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from src.ingestion.common.numbers import normalize_unit

LEXICON_PATH = Path(__file__).resolve().parents[1] / "data" / "tep_lexicon.json"
_UNIT_TAIL_RE = re.compile(r"[,(]\s*([^,()]{1,12}?)\s*\)?\s*$")


def squash(s: str) -> str:
    """Case-, 'ё'-, space- and punctuation-insensitive form of a label."""
    return re.sub(r"[\W_]+", "", s.lower().replace("ё", "е"))


def _flatten(by_source: dict) -> list[str]:
    return [x for items in by_source.values() for x in items]


@dataclass(frozen=True, eq=False)  # hashed by identity (cached patterns)
class Lexicon:
    field_units: dict[str, str]
    table_labels: dict[str, list[str]]  # field -> squashed labels (all languages)
    text_labels: dict[str, list[str]]  # field -> labels as written
    number_first: dict[str, list[str]]  # field -> labels that follow the number
    units: dict[str, list[str]]  # canonical unit -> spellings
    number_headers: list[str]
    units_row: list[str]
    total_row: list[str]
    raw_labels: dict[str, list[str]]  # field -> table and text labels as written
    negatives: list[str]  # labels of quantities that are not TEP ("Площадь участка")

    def field_of(self, label: str) -> str | None:
        """Field whose longest label occurs in `label` (ignoring spaces/punctuation)."""
        s = squash(label)
        best, best_len = None, 0
        for fld, labels in self.table_labels.items():
            for lab in labels:
                if lab and lab in s and len(lab) > best_len:
                    best, best_len = fld, len(lab)
        return best

    def unit_of(self, text: str) -> str | None:
        s = squash(text)
        if not s:
            return None
        for canon, spellings in self.units.items():
            if any(s == squash(u) for u in spellings):
                return canon
        return normalize_unit(text)

    def unit_in(self, text: str) -> str | None:
        """Unit named after a comma or in brackets at the end of a header: 'Площадь застройки, м²'."""
        m = _UNIT_TAIL_RE.search(text)
        return self.unit_of(m.group(1)) if m else None

    def is_total(self, text: str) -> bool:
        return any(squash(text).startswith(squash(t)) for t in self.total_row)

    def is_units_row(self, text: str) -> bool:
        return any(squash(text).startswith(squash(t)) for t in self.units_row)


@cache
def load_lexicon(path: Path = LEXICON_PATH) -> Lexicon:
    data = json.loads(path.read_text(encoding="utf-8"))
    fields = data["fields"]

    def per_field(key: str, squashed: bool) -> dict[str, list[str]]:
        out = {}
        for fld, spec in fields.items():
            labels = [x for lang in spec.get(key, {}).values() for x in _flatten(lang)]
            labels = list(dict.fromkeys(squash(x) if squashed else x.lower() for x in labels))
            if labels:
                out[fld] = labels
        return out

    raw = {fld: list(dict.fromkeys(x for key in ("table", "text") for lang in spec.get(key, {}).values()
                                   for x in _flatten(lang)))
           for fld, spec in fields.items()}
    h = data["headers"]
    return Lexicon(
        field_units={f: spec["unit"] for f, spec in fields.items()},
        table_labels=per_field("table", True),
        text_labels=per_field("text", False),
        number_first=per_field("text_number_first", False),
        units={u: list(dict.fromkeys(_flatten(v))) for u, v in data["units"].items()},
        number_headers=_flatten(h["number"]),
        units_row=_flatten(h["units_row"]),
        total_row=_flatten(h["total_row"]),
        raw_labels={f: labs for f, labs in raw.items() if labs},
        negatives=_flatten(data.get("negatives", {})),
    )
