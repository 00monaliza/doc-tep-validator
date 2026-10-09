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

import math
import re
from dataclasses import dataclass

from src.ner.common.lexicon import Lexicon, squash

METHODS = ("exact", "fuzzy", "embedding")
_LETTER_RE = re.compile(r"[^\W\d_]")
FUZZY_MIN = 0.85  # share of a label's (weighted) words found in the text; tuned on v3-dev
FUZZY_MARGIN = 0.3  # over the next field or a negative label
NEGATIVE = "_negative"  # pseudo-field of lexicon "negatives" ("Площадь участка")
HOMOGLYPHS = str.maketrans("aceopxyki", "асеорхукі")  # Latin letters OCR puts into Cyrillic words
EMBED_MIN = 0.88  # cosine to the nearest lexicon label; tuned on v3-dev
EMBED_MARGIN = 0.01  # over the best label of another field (a closer negative blocks outright)
EMBED_EVIDENCE = 0.3  # fuzzy evidence needed before asking the model (keeps cell names like "Гараж" out)
EMBED_MAX_LEN = 80
# words that name a kind of quantity, not which one: "Количество квартир", "Стоимость оборудования",
# "Объём бетона" share them with TEP labels. On their own they are no evidence for a field.
QUANTITY_NOUNS = ("площадь", "объем", "количество", "число", "стоимость", "продолжительность", "срок",
                  "аудан", "алаң", "көлем", "саны", "құн", "ұзақтығы", "мерзім")
EMBED_UNAVAILABLE = ("Модель для незнакомых названий показателей не найдена (scripts/fetch_models.py): "
                     "показатели распознаны по словарю и нечёткому сопоставлению.")
SYMBOLS = {"s": "площадь", "v": "объем"}  # "S общ.", "V стр."
# a word, a contraction "кол-во" / "ст-ть", and a truncation dot
_TOKEN_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]{1,3}(?![^\W\d_]))?\.?")


def tokens(text: str) -> list[tuple[str, bool]]:
    """(normalised word, is a truncation): 'Пл.' -> ('пл', True), 'кол-во' -> ('кол', True)."""
    out = []
    for m in _TOKEN_RE.finditer(text):
        raw = m.group().lower()
        bare = raw.rstrip(".")
        if bare in SYMBOLS:  # before the look-alike mapping: Latin S, V
            out.append((SYMBOLS[bare], False))
            continue
        word = raw.translate(HOMOGLYPHS).replace("ё", "е")
        abbrev = word.endswith(".") or "-" in word
        word = word.split("-")[0].rstrip(".")
        if len(word) >= 2:
            out.append((word, abbrev))
    return out


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        n += 1
    return n


def _one_edit(a: str, b: str) -> bool:
    """Levenshtein distance <= 1."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = _common_prefix(a, b)
    return a[i + 1:] == b[i + 1:] if len(a) == len(b) else a[i:] == b[i + 1:]


def word_matches(token: str, abbrev: bool, word: str) -> bool:
    """Same word up to inflection (a prefix covering all but the ending), one OCR edit, or a truncation of it.
    'общей' ~ 'общая', 'этажей' ~ 'этажность'; not 'застекления' ~ 'застройки', 'пола' ~ 'полезная'."""
    if abbrev and len(token) >= 2 and word.startswith(token):
        return True
    cp, short, long_ = _common_prefix(token, word), min(len(token), len(word)), max(len(token), len(word))
    if cp >= max(4, short - 3) or (cp >= 3 and cp >= short - 2 and long_ <= 6):
        return True
    return short >= 5 and _one_edit(token, word)


def _quantity_noun(word: str) -> bool:
    return any(word_matches(word, False, q) for q in QUANTITY_NOUNS)


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
        # a one-word label that is only a quantity noun ("объём") names a field verbatim (exact stage) but is
        # no fuzzy prototype: it would cover "Объём засыпки" completely; "Этажность" stays
        self._labels = [(f, ws) for f, labs in lex.raw_labels.items() for lab in labs
                        if (ws := tokens(lab)) and not (len(ws) == 1 and _quantity_noun(ws[0][0]))]
        self._labels += [(NEGATIVE, ws) for lab in lex.negatives if (ws := tokens(lab))]
        vocab = {w for _, ws in self._labels for w, _ in ws}
        n = len(lex.field_units)
        df = {w: len({f for f, ws in self._labels if f != NEGATIVE and any(word_matches(w, False, x) for x, _ in ws)})
              for w in vocab}
        self._weight = {w: math.log(1 + n / max(df[w], 1)) for w in vocab}  # rarer across fields = heavier
        self._prototypes = [(f, lab) for f, labs in lex.raw_labels.items() for lab in labs]
        self._prototypes += [(NEGATIVE, lab) for lab in lex.negatives]

    def match(self, text: str, unit: str | None = None, where: str = "table") -> Match | None:
        """Field named by `text` (a table cell, or the words next to a number when `where='text'`)."""
        key = (text, unit, where)
        if key not in self._memo:
            self._memo[key] = self._match(text, unit, where)
        return self._memo[key]

    @property
    def embedder(self):
        if self._embedder is None:
            from src.ner.common.label_embed import get_embedder

            self._embedder = get_embedder()
        return self._embedder

    def _embedding(self, text: str, allowed: set[str]) -> Match | None:
        if not self.embedder.available():
            if EMBED_UNAVAILABLE not in self.warnings:
                self.warnings.append(EMBED_UNAVAILABLE)
            return None
        vecs = self.embedder.embed([text] + [lab for _, lab in self._prototypes])
        sims = (vecs[1:] @ vecs[0]).tolist()
        best: dict[str, float] = {}
        for (f, _), s in zip(self._prototypes, sims, strict=True):
            if f == NEGATIVE or f in allowed:
                best[f] = max(best.get(f, -1.0), s)
        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
        top_f, top = ranked[0]
        if top_f == NEGATIVE:  # closest to a known non-TEP quantity
            return None
        second = max((v for f, v in ranked[1:] if f != NEGATIVE), default=-1.0)  # margin over another field
        if top >= EMBED_MIN and top - second >= EMBED_MARGIN:
            return Match(top_f, round(top, 3), "embedding")
        return None

    def _allowed(self, unit: str | None) -> set[str]:
        if unit is None or not self.unit_check:
            return set(self.lex.field_units)
        return {f for f, u in self.lex.field_units.items() if u == unit}

    def _exact(self, text: str, allowed: set[str], where: str) -> Match | None:
        s = squash(text)
        best, best_len = None, 0
        for fld in allowed:
            for lab in self._exact_labels[where].get(fld, ()):
                if lab and lab in s and len(lab) > best_len:
                    best, best_len = fld, len(lab)
        return Match(best, 1.0, "exact") if best else None

    def _coverage(self, text: str, allowed: set[str]) -> tuple[dict[str, float], dict[str, int]]:
        """Per field (and NEGATIVE): the best weighted share of one label's words found in the text,
        and how many of the found words are not quantity nouns."""
        toks = tokens(text)
        cover: dict[str, float] = {}
        words_hit: dict[str, int] = {}
        for f, words in self._labels:
            if f != NEGATIVE and f not in allowed:
                continue
            # a truncation in a label ('S застр.') needs the text word to start with it; negatives need
            # full words, so 'Пл. застр.' is not read as 'Плотность застройки'
            found = [w for w, w_abbrev in words
                     if any(t.startswith(w) if w_abbrev else word_matches(t, a and f != NEGATIVE, w) for t, a in toks)]
            total = sum(self._weight[w] for w, _ in words)
            share = sum(self._weight[w] for w in found) / total if total else 0.0
            if share > cover.get(f, -1.0):
                cover[f], words_hit[f] = share, sum(not _quantity_noun(w) for w in found)
        return cover, words_hit

    def _negative(self, cover: dict[str, float]) -> bool:
        """A lexicon negative ("Площадь участка", "Объём бетона") describes the text better than any field."""
        neg = cover.get(NEGATIVE, 0.0)
        return neg >= FUZZY_MIN and neg >= max((s for f, s in cover.items() if f != NEGATIVE), default=0.0)

    def _fuzzy(self, cover: dict[str, float], words_hit: dict[str, int]) -> tuple[Match | None, float]:
        """(match, evidence): evidence is the best coverage among fields with a found word that is not a
        quantity noun ("застройки", "этажей", "строительства")."""
        ranked = sorted(cover.items(), key=lambda kv: kv[1], reverse=True)
        if not ranked or ranked[0][1] == 0:
            return None, 0.0
        (top_f, top), second = ranked[0], ranked[1][1] if len(ranked) > 1 else 0.0
        evidence = max((s for f, s in ranked if f != NEGATIVE and words_hit[f] >= 1), default=0.0)
        if top_f != NEGATIVE and top >= FUZZY_MIN and top - second >= FUZZY_MARGIN:
            return Match(top_f, round(top, 3), "fuzzy"), evidence
        return None, evidence

    def _match(self, text: str, unit: str | None, where: str) -> Match | None:
        allowed = self._allowed(unit)
        if not allowed or not _LETTER_RE.search(text):
            return None
        cover, words_hit = self._coverage(text, allowed) if "fuzzy" in self.methods else ({}, {})
        if self._negative(cover):
            return None
        if m := self._exact(text, allowed, where):
            return m
        if "fuzzy" not in self.methods:
            return None
        m, evidence = self._fuzzy(cover, words_hit)
        if m or "embedding" not in self.methods or where != "table":
            return m
        if evidence >= EMBED_EVIDENCE and len(text) <= EMBED_MAX_LEN:
            return self._embedding(text, allowed)
        return None
