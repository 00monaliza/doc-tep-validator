"""Rule-based TEP extraction baseline for text-layer PDFs (RU/KZ).

The honest ceiling of hand-written rules that a learned extractor will be
compared with. All surface forms come from ``src/ner/data/tep_lexicon.json``;
the code only knows table and sentence *structure*:

* **tables** are read by their headers, never by column position. A table whose
  header row names two or more TEP fields is *horizontal* (fields are columns,
  rows are objects); a table with a column of TEP labels is *vertical* (fields
  are rows, the value column is found by content: the non-label, non-unit,
  non-"№" column with most numbers). Header words broken by narrow columns are
  glued (``ingestion.real``) and labels are matched ignoring spaces and
  punctuation, so an unglued break still matches;
* **sentences**: label … number unit (RU and KZ) and number unit … label
  (Kazakh word order, "1 124,98 м³ құрылыс көлемі"); for floors the number
  precedes the label ("3-этажное", "2 қабатты");
* **objects** (buildings) come from numbered headings and from row labels of
  horizontal tables; a value's object is the row label, the section heading or
  a mention in the sentence (``crossvalidation.objects``). Values outside any
  building go to the pseudo-object ``project``; if the document describes one
  building only, they are attributed to it.

Which field a label names is decided by ``label_match.LabelMatcher``; ``stages``
switches on its steps for the ablation (``exact`` alone is the original
baseline). When a field of an object is stated several times, a horizontal
table wins over a vertical table, any table wins over a sentence (text mentions
often repeat, round or contradict the tables), and an exact label over a fuzzy
or embedded one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cache

from src.crossvalidation.objects import ObjectIndex, PageText, build_index, object_headings, page_texts, resolve
from src.ingestion.common.numbers import M2_IN_TEXT, M3_IN_TEXT, NUMBER_RE, number_readings
from src.ingestion.real import Page, PageTable, norm_ws
from src.ner.common.label_match import METHODS, LabelMatcher, Match
from src.ner.common.lexicon import LEXICON_PATH, Lexicon, load_lexicon, squash  # noqa: F401  (re-exported)

PROJECT = "project"
PRIORITY = {"table_h": 0, "table_v": 1, "text": 2}
STAGES = ("exact", "anchor", "fuzzy", "embedding")  # ablation order; extract() takes a prefix


@dataclass
class Candidate:
    object: str  # object id (obj1...) or PROJECT
    field: str
    value: float
    source: str  # table_h | table_v | text
    page: int
    quote: str
    method: str = "exact"  # label_match stage that named the field
    score: float = 1.0

    @property
    def priority(self) -> int:
        return PRIORITY[self.source]

    @property
    def rank(self) -> tuple[int, int, float]:
        """Lower wins: horizontal table < vertical table < text, then exact < fuzzy < embedding."""
        return PRIORITY[self.source], METHODS.index(self.method), -self.score


@dataclass
class Extraction:
    objects: dict[str, str]  # id -> name, PROJECT included
    candidates: list[Candidate] = field(default_factory=list)
    slots: dict[tuple[str, str], Candidate] = field(default_factory=dict)  # (object, field) -> chosen value
    warnings: list[str] = field(default_factory=list)


def _value(cell: str, fld: str, lex: Lexicon) -> float | None:
    readings = number_readings(cell)
    if not readings:
        return None
    value = readings[0]
    if lex.field_units.get(fld) in ("floor", "month") and not float(value).is_integer():
        return None
    return value


def _label(row: list[str]) -> str:
    return next((c for c in row if re.search(r"[^\W\d_]", c)), "")


# ------------------------------------------------------------------ tables
def _horizontal_fields(table: PageTable, lex: Lexicon, matcher: LabelMatcher) -> tuple[int, dict[int, Match]] | None:
    """(header row index, column -> match) if a row among the first three names >= 2 fields.
    A column's unit comes from its header ('Площадь, м²') or from a units row right below."""
    for i, row in enumerate(table.rows[:3]):
        cells = table.header if i == 0 else row
        below = table.rows[i + 1] if i + 1 < len(table.rows) else []
        units = below if below and lex.is_units_row(_label(below)) else []
        cols = {}
        for c, cell in enumerate(cells):
            if not cell:
                continue
            unit = lex.unit_in(cell) or (lex.unit_of(units[c]) if c < len(units) else None)
            if m := matcher.match(cell, unit):
                cols[c] = m
        if len({m.field for m in cols.values()}) >= 2:
            return i, cols
    return None


def _horizontal(table: PageTable, lex: Lexicon, matcher: LabelMatcher, index: ObjectIndex, ctx: str | None,
                row_objects: dict[str, str]) -> list[tuple[str | None, str, Match, float, list[str]]]:
    """(object id, row label, match, value, row) for every data cell of a horizontal table."""
    found = _horizontal_fields(table, lex, matcher)
    if found is None:
        return []
    h, cols = found
    data_rows = []
    for row in table.rows[h + 1:]:
        label = _label(row)
        if (label and (lex.is_total(label) or lex.is_units_row(label))) or \
                not any(_value(row[c], m.field, lex) is not None for c, m in cols.items() if c < len(row)):
            continue
        data_rows.append((label, row))
    out = []
    for label, row in data_rows:
        named = index.mentioned(label) if label else set()
        if len(data_rows) == 1 and ctx is not None:
            obj = ctx  # a single-row table inside a building's section describes that building
        elif len(named) == 1:
            obj = next(iter(named))
        elif label and squash(label) in row_objects:
            obj = row_objects[squash(label)]
        else:
            obj = ctx
        for c, m in cols.items():
            v = _value(row[c], m.field, lex) if c < len(row) else None
            if v is not None:
                out.append((obj, label, m, v, row))
    return out


def _vertical(table: PageTable, lex: Lexicon, matcher: LabelMatcher) -> list[tuple[Match, float, list[str]]]:
    """(match, value, row) for a table with a column of TEP labels; a row's unit comes from the units column."""
    rows = table.rows
    n_cols = max(len(r) for r in rows)
    header = table.header
    skip, unit_col = set(), None
    for c in range(n_cols):
        head = header[c] if c < len(header) else ""
        cells = [r[c] for r in rows[1:] if c < len(r) and r[c]]
        if any(squash(head) == squash(h) for h in lex.number_headers):
            skip.add(c)
        elif cells and sum(lex.unit_of(x) is not None for x in cells) >= len(cells) / 2:
            skip.add(c)
            unit_col = c

    def unit(row: list[str]) -> str | None:
        return lex.unit_of(row[unit_col]) if unit_col is not None and unit_col < len(row) else None

    matches = {c: [matcher.match(r[c], unit(r)) if c < len(r) and r[c] else None for r in rows]
               for c in range(n_cols) if c not in skip}
    hits = {c: sum(m is not None for m in ms) for c, ms in matches.items()}
    if not hits:
        return []
    label_col = max(hits, key=lambda c: hits[c])
    if hits[label_col] < 2:
        return []
    skip.add(label_col)
    numeric = {c: sum(number_readings(r[c]) != () for r in rows[1:] if c < len(r))
               for c in range(n_cols) if c not in skip}
    if not numeric:
        return []
    value_col = max(numeric, key=lambda c: numeric[c])
    out = []
    for row, m in zip(rows, matches[label_col], strict=True):
        if m is not None and value_col < len(row) and (v := _value(row[value_col], m.field, lex)) is not None:
            out.append((m, v, row))
    return out


def _row_quote(pt: PageText, row: list[str], cell: str) -> str:
    joined = norm_ws(" ".join(c for c in row if c))
    return joined if joined in pt.text else cell


# ------------------------------------------------------------------ sentences
def _stem_pattern(label: str) -> str:
    words = re.split(r"\s+", label.strip().lower().replace("ё", "е"))
    parts = [re.escape(w[: max(4, len(w) - 2)]) + r"\w*" if len(w) > 4 else re.escape(w) + r"\w*" for w in words]
    return r"\s+".join(parts)


@cache
def _text_patterns(lex: Lexicon) -> list[tuple[str, re.Pattern[str], str]]:
    """(field, regex, direction); every regex has groups 'num' and 'unit' (or no unit for floors)."""
    num = rf"(?P<num>{NUMBER_RE.pattern})"
    out = []
    for fld, labels in lex.text_labels.items():
        spellings = sorted(lex.units[lex.field_units[fld]], key=len, reverse=True)
        unit = "(?P<unit>" + "|".join(re.escape(u).replace(r"\ ", r"\s?") for u in spellings) + r")(?![^\W\d_]|/)"
        for label in labels:
            lab = _stem_pattern(label)
            out.append((fld, re.compile(rf"(?<![^\W\d_]){lab}[^\d.;:]{{0,60}}?{num}\s*{unit}", re.IGNORECASE),
                        "label_first"))
            out.append((fld, re.compile(rf"{num}\s*{unit}\s+(?:[^\W\d_]+\s+){{0,1}}{lab}", re.IGNORECASE),
                        "number_first"))
    for fld, labels in lex.number_first.items():
        for label in labels:
            out.append((fld, re.compile(rf"(?P<num>\d{{1,2}})\s*-?\s*{_stem_pattern(label)}", re.IGNORECASE),
                        "number_first"))
    return out


def _text(pts: list[PageText], index: ObjectIndex, lex: Lexicon) -> list[Candidate]:
    out, seen = [], set()
    for pt in pts:
        text = pt.text.replace("ё", "е").replace("Ё", "Е")  # same length: offsets stay valid
        for fld, rx, _ in _text_patterns(lex):
            for m in rx.finditer(text):
                value = _value(m.group("num"), fld, lex)
                if value is None:
                    continue
                s, e = m.span("num")
                if (pt.page, s) in seen:  # one number, one field
                    continue
                seen.add((pt.page, s))
                obj, _ = resolve(pt, index, m.start(), m.end())
                out.append(Candidate(obj or PROJECT, fld, value, "text", pt.page, pt.text[m.start():m.end()]))
    return out


TEXT_WINDOW = 120  # characters searched for the label on each side of a number
TEXT_UNITS = ("m2", "m3", "kKZT", "month")  # floors: "3-этажное" patterns
EXTRA_UNIT_FORMS = {"m2": [M2_IN_TEXT], "m3": [M3_IN_TEXT]}
# end of a clause: sentence end before a capital letter, ';', or ', ' (a decimal comma has no space)
BOUNDARY_RE = re.compile(r"[.!?]\s+(?=[A-ZА-ЯЁӘҒҚҢӨҰҮҺІ])|;|,\s")


def _spelling(s: str) -> str:
    return re.escape(s.strip()).replace(r"\.", r"\.?\s?").replace(r"\ ", r"\s?")


@cache
def _anchor_re(lex: Lexicon) -> re.Pattern[str]:
    """A number followed by a TEP unit in any spelling; the unit's group is named by its canonical id."""
    groups = []
    for canon in TEXT_UNITS:
        forms = [_spelling(s) for s in sorted(lex.units.get(canon, ()), key=len, reverse=True)]
        groups.append(f"(?P<{canon}>{'|'.join(forms + EXTRA_UNIT_FORMS.get(canon, []))})")
    return re.compile(rf"(?P<num>{NUMBER_RE.pattern})\s*(?:{'|'.join(groups)})(?![^\W\d_]|\d)", re.IGNORECASE)


def _left_start(text: str, start: int, floor: int) -> int:
    lo = max(floor, start - TEXT_WINDOW)
    for b in BOUNDARY_RE.finditer(text, lo, start):
        lo = b.end()
    return lo


def _right_end(text: str, end: int) -> int:
    hi = min(len(text), end + TEXT_WINDOW)
    b = BOUNDARY_RE.search(text, end, hi)
    return b.start() if b else hi


def _text_anchored(pts: list[PageText], index: ObjectIndex, lex: Lexicon, matcher: LabelMatcher) -> list[Candidate]:
    """Sentence TEP read from the number: every 'number + TEP unit' is named by the words before it
    (or after it, Kazakh order), up to a clause boundary or the previous number."""
    out, seen = [], set()
    for pt in pts:
        text = pt.text.replace("ё", "е").replace("Ё", "Е")  # same length: offsets stay valid
        prev_end = 0
        for m in _anchor_re(lex).finditer(text):
            unit = next(k for k in TEXT_UNITS if m.group(k))
            s = m.start("num")
            lo = _left_start(text, s, prev_end)
            found, qs, qe = matcher.match(text[lo:s], unit, where="text"), lo, m.end()
            if found is None:
                hi = _right_end(text, m.end())
                found, qs, qe = matcher.match(text[m.end():hi], unit, where="text"), s, hi
            prev_end = m.end()
            if found is None or (pt.page, s) in seen:
                continue
            value = _value(m.group("num"), found.field, lex)
            if value is None:
                continue
            seen.add((pt.page, s))
            obj, _ = resolve(pt, index, qs, qe)
            out.append(Candidate(obj or PROJECT, found.field, value, "text", pt.page, pt.text[qs:qe].strip(),
                                 found.method, found.score))
        for fld, rx, _ in _text_patterns(lex):  # floors: "3-этажное", "2 қабатты"
            if lex.field_units[fld] != "floor":
                continue
            for m in rx.finditer(text):
                s = m.start("num")
                if (pt.page, s) in seen or (value := _value(m.group("num"), fld, lex)) is None:
                    continue
                seen.add((pt.page, s))
                obj, _ = resolve(pt, index, m.start(), m.end())
                out.append(Candidate(obj or PROJECT, fld, value, "text", pt.page, pt.text[m.start():m.end()]))
    return out


# ------------------------------------------------------------------ main
def object_index(pages: list[Page], lex: Lexicon | None = None, matcher: LabelMatcher | None = None) -> ObjectIndex:
    """Objects of a document: numbered building headings, plus the row labels of horizontal
    TEP tables with several data rows (a summary table names buildings whose headings lack
    a building noun: "Шаруашылық блогы", "Гараж")."""
    lex = lex or load_lexicon()
    matcher = matcher or LabelMatcher(lex, methods=("exact",), unit_check=False)
    headings = object_headings(pages)
    row_names: list[str] = []
    empty = build_index([])
    for page in pages:
        for table in page.tables:
            rows = _horizontal(table, lex, matcher, empty, None, {})
            labels = {label for _, label, *_ in rows if label}
            if len(labels) >= 2:
                row_names += [x for x in labels if squash(x) not in {squash(n) for n in headings + row_names}]
    return build_index(headings + sorted(set(row_names), key=row_names.index))


def extract(pages: list[Page], lex: Lexicon | None = None, stages: tuple[str, ...] = STAGES) -> Extraction:
    """TEP candidates and the chosen value per (object, field). `stages` is a prefix of STAGES (ablation)."""
    assert stages == STAGES[: len(stages)], stages
    lex = lex or load_lexicon()
    matcher = LabelMatcher(lex, methods=tuple(s for s in stages if s in METHODS), unit_check="anchor" in stages)
    index = object_index(pages, lex, matcher)
    names = {o.id: o.name for o in index.objects}
    row_objects = {squash(o.name): o.id for o in index.objects}
    pts = page_texts(pages, index)
    carried = [None] + [pt.ctx_after for pt in pts[:-1]]

    cands: list[Candidate] = []
    for page, pt, car in zip(pages, pts, carried, strict=True):
        for table in page.tables:
            ctx = pt.context_above(table.top, car)
            h_rows = _horizontal(table, lex, matcher, index, ctx, row_objects)
            for obj, _, m, v, row in h_rows:
                cands.append(Candidate(obj or PROJECT, m.field, v, "table_h", page.number,
                                       _row_quote(pt, row, ""), m.method, m.score))
            if not h_rows:
                for m, v, row in _vertical(table, lex, matcher):
                    cands.append(Candidate(ctx or PROJECT, m.field, v, "table_v", page.number,
                                           _row_quote(pt, row, ""), m.method, m.score))
    cands += _text_anchored(pts, index, lex, matcher) if "anchor" in stages else _text(pts, index, lex)

    buildings = [o for o in names if o != PROJECT]
    if len(buildings) == 1:  # one building: the general values are its values
        for c in cands:
            if c.object == PROJECT:
                c.object = buildings[0]
    result = Extraction(names | {PROJECT: "Проект в целом"}, cands, warnings=matcher.warnings)
    for c in sorted(cands, key=lambda c: c.rank):
        result.slots.setdefault((c.object, c.field), c)
    return result
