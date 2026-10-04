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

When a field of an object is stated several times, a horizontal table wins over
a vertical table, and any table wins over a sentence: text mentions often
repeat, round or contradict the tables.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from src.crossvalidation.objects import ObjectIndex, PageText, build_index, object_headings, page_texts, resolve
from src.ingestion.common.numbers import NUMBER_RE, number_readings
from src.ingestion.real import Page, PageTable, norm_ws

LEXICON_PATH = Path(__file__).resolve().parents[1] / "data" / "tep_lexicon.json"
PROJECT = "project"
PRIORITY = {"table_h": 0, "table_v": 1, "text": 2}


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
        return None

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
    )


@dataclass
class Candidate:
    object: str  # object id (obj1...) or PROJECT
    field: str
    value: float
    source: str  # table_h | table_v | text
    page: int
    quote: str

    @property
    def priority(self) -> int:
        return PRIORITY[self.source]


@dataclass
class Extraction:
    objects: dict[str, str]  # id -> name, PROJECT included
    candidates: list[Candidate] = field(default_factory=list)
    slots: dict[tuple[str, str], Candidate] = field(default_factory=dict)  # (object, field) -> chosen value


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
def _horizontal_fields(table: PageTable, lex: Lexicon) -> tuple[int, dict[int, str]] | None:
    """(header row index, column -> field) if a row among the first three names >= 2 fields."""
    for i, row in enumerate(table.rows[:3]):
        cells = table.header if i == 0 else row
        cols = {c: f for c, cell in enumerate(cells) if cell and (f := lex.field_of(cell))}
        if len(set(cols.values())) >= 2:
            return i, cols
    return None


def _horizontal(table: PageTable, lex: Lexicon, index: ObjectIndex, ctx: str | None,
                row_objects: dict[str, str]) -> list[tuple[str | None, str, str, float, list[str]]]:
    """(object id, row label, field, value, row) for every data cell of a horizontal table."""
    found = _horizontal_fields(table, lex)
    if found is None:
        return []
    h, cols = found
    data_rows = []
    for row in table.rows[h + 1:]:
        label = _label(row)
        if (label and (lex.is_total(label) or lex.is_units_row(label))) or \
                not any(_value(row[c], f, lex) is not None for c, f in cols.items() if c < len(row)):
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
        for c, f in cols.items():
            v = _value(row[c], f, lex) if c < len(row) else None
            if v is not None:
                out.append((obj, label, f, v, row))
    return out


def _vertical(table: PageTable, lex: Lexicon) -> list[tuple[str, float, list[str]]]:
    """(field, value, row) for a table with a column of TEP labels."""
    rows = table.rows
    n_cols = max(len(r) for r in rows)
    label_hits = [sum(1 for r in rows if c < len(r) and lex.field_of(r[c])) for c in range(n_cols)]
    label_col = max(range(n_cols), key=lambda c: label_hits[c])
    if label_hits[label_col] < 2:
        return []
    header = table.header
    skip = {label_col}
    for c in range(n_cols):
        head = header[c] if c < len(header) else ""
        cells = [r[c] for r in rows[1:] if c < len(r) and r[c]]
        if any(squash(head) == squash(h) for h in lex.number_headers):
            skip.add(c)
        elif cells and sum(lex.unit_of(x) is not None for x in cells) >= len(cells) / 2:
            skip.add(c)
    numeric = {c: sum(number_readings(r[c]) != () for r in rows[1:] if c < len(r))
               for c in range(n_cols) if c not in skip}
    if not numeric:
        return []
    value_col = max(numeric, key=lambda c: numeric[c])
    out = []
    for row in rows:
        if label_col >= len(row) or value_col >= len(row):
            continue
        f = lex.field_of(row[label_col])
        if f is not None and (v := _value(row[value_col], f, lex)) is not None:
            out.append((f, v, row))
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


# ------------------------------------------------------------------ main
def extract(pages: list[Page], lex: Lexicon | None = None) -> Extraction:
    lex = lex or load_lexicon()
    headings = object_headings(pages)
    # row labels of horizontal tables with several data rows name objects too
    row_names: list[str] = []
    empty = build_index([])
    for page in pages:
        for table in page.tables:
            rows = _horizontal(table, lex, empty, None, {})
            labels = {label for _, label, *_ in rows if label}
            if len(labels) >= 2:
                row_names += [x for x in labels if squash(x) not in {squash(n) for n in headings + row_names}]
    index = build_index(headings + sorted(set(row_names), key=row_names.index))
    names = {o.id: o.name for o in index.objects}
    row_objects = {squash(o.name): o.id for o in index.objects}
    pts = page_texts(pages, index)
    carried = [None] + [pt.ctx_after for pt in pts[:-1]]

    cands: list[Candidate] = []
    for page, pt, car in zip(pages, pts, carried, strict=True):
        for table in page.tables:
            ctx = pt.context_above(table.top, car)
            h_rows = _horizontal(table, lex, index, ctx, row_objects)
            for obj, _, f, v, row in h_rows:
                cands.append(Candidate(obj or PROJECT, f, v, "table_h", page.number, _row_quote(pt, row, "")))
            if not h_rows:
                for f, v, row in _vertical(table, lex):
                    cands.append(Candidate(ctx or PROJECT, f, v, "table_v", page.number, _row_quote(pt, row, "")))
    cands += _text(pts, index, lex)

    buildings = [o for o in names if o != PROJECT]
    if len(buildings) == 1:  # one building: the general values are its values
        for c in cands:
            if c.object == PROJECT:
                c.object = buildings[0]
    result = Extraction(names | {PROJECT: "Проект в целом"}, cands)
    for c in sorted(cands, key=lambda c: c.priority):
        result.slots.setdefault((c.object, c.field), c)
    return result
