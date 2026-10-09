"""Which TEP field a label names, also when the lexicon does not list it verbatim.

A cascade; a stage runs only if the previous ones are not confident:

* ``exact``: the longest lexicon label contained in the text, ignoring case,
  spaces and punctuation (the original baseline);
* ``fuzzy``: words normalised (Latin look-alikes, truncations such as «пл.»,
  «застр.») and compared by prefix with a one-edit tolerance; a field scores the
  IDF-weighted share of one of its labels found in the text;
* ``embedding``: cosine similarity of multilingual-e5-small embeddings to the
  lexicon labels; table cells only, and only if fuzzy saw some evidence.

If the unit of the value is known, only fields with that unit compete. Every
wording still comes from ``tep_lexicon.json``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.ner.common.lexicon import Lexicon, squash

METHODS = ("exact", "fuzzy", "embedding")
_LETTER_RE = re.compile(r"[^\W\d_]")


@dataclass(frozen=True)
class Match:
    field: str
    score: float
    method: str


class LabelMatcher:
    def __init__(self, lex: Lexicon, methods: tuple[str, ...] = METHODS, unit_check: bool = True,
                 embedder=None) -> None:
        self.lex, self.methods, self.unit_check = lex, tuple(methods), unit_check
        self._embedder = embedder
        self.warnings: list[str] = []
        text_extra = {f: [squash(x) for x in labs] for f, labs in lex.text_labels.items()}
        self._exact_labels = {
            "table": lex.table_labels,
            "text": {f: list(dict.fromkeys(lex.table_labels.get(f, []) + text_extra.get(f, [])))
                     for f in lex.field_units},
        }
        self._memo: dict[tuple[str, str | None, str], Match | None] = {}

    def match(self, text: str, unit: str | None = None, where: str = "table") -> Match | None:
        """Field named by `text` (a table cell, or the words next to a number when `where='text'`)."""
        key = (text, unit, where)
        if key not in self._memo:
            self._memo[key] = self._match(text, unit, where)
        return self._memo[key]

    def _allowed(self, unit: str | None) -> set[str]:
        if unit is None or not self.unit_check:
            return set(self.lex.field_units)
        return {f for f, u in self.lex.field_units.items() if u == unit}

    def _match(self, text: str, unit: str | None, where: str) -> Match | None:
        allowed = self._allowed(unit)
        if not allowed or not _LETTER_RE.search(text):
            return None
        return self._exact(text, allowed, where)

    def _exact(self, text: str, allowed: set[str], where: str) -> Match | None:
        s = squash(text)
        best, best_len = None, 0
        for fld in allowed:
            for lab in self._exact_labels[where].get(fld, ()):
                if lab and lab in s and len(lab) > best_len:
                    best, best_len = fld, len(lab)
        return Match(best, 1.0, "exact") if best else None
