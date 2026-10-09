"""Rule-based checks v1 for real documents, run after v0 (``rules.py``) on the same pages.

* ``VALUE_CROSS_SECTION_MISMATCH`` (``absolute_elevation_m``) — elevation 0.000 of a building outside the
  site relief range;
* ``TEP_CALCULATION_METHOD`` (``construction_volume_m3``) — volume equal to building area x clear height, or an
  implausibly low average storey height;
* ``COPY_PASTE_LABEL`` (``object_label``) — the ТЭП table of building X names another building;
* ``PARAMETER_CONTRADICTION`` (``blind_area``, ``roof``) — one building parameter stated differently;
  parameters come from ``ner/data/parameter_lexicon.json``.

Like v0, nothing here knows the concrete document; a check without its inputs does not fire.
"""

from __future__ import annotations

import re

from src.crossvalidation.objects import OBJECT_NOUN_RE, ObjectIndex, PageText, resolve
from src.crossvalidation.rules import Mention, _finding, _quote
from src.evaluation.schema import Finding, Ref
from src.ingestion.common.numbers import NUMBER_RE, number_readings
from src.ingestion.real import Page
from src.ner.common.parameters import load_parameters, width_mm
from src.ner.common.taxonomy import DiscrepancyType

ELEVATION_SLACK_M = 3.0  # a building rarely sits higher above (or below) the relief than this


def _n(name: str) -> str:
    return rf"(?P<{name}>{NUMBER_RE.pattern})"


Z_RE = [
    re.compile(rf"абсолютн\w*\s+отметк\w*\s*[-–—:=]?\s*{_n('z')}", re.IGNORECASE),
    re.compile(rf"{_n('z')}\s*м?\s+абсолютт\w*\s+белгі", re.IGNORECASE),
]
RELIEF_RE = [
    re.compile(rf"отметк\w*[^.;]{{0,80}}?от\s+{_n('lo')}\s*м?\s*до\s+{_n('hi')}", re.IGNORECASE),
    re.compile(rf"белгілер\w*[^.;]{{0,40}}?{_n('lo')}\s*м?-?(?:ден|дан|тен|тан)\s+{_n('hi')}",
               re.IGNORECASE),
]


def _num(text: str) -> float | None:
    readings = number_readings(text)
    return readings[0] if readings else None


def _object(pt: PageText, index: ObjectIndex, start: int, end: int) -> str | None:
    obj, _ = resolve(pt, index, start, end)
    if obj is None and len(index.objects) == 1:
        return index.objects[0].id
    return obj


def check_elevation(pts: list[PageText], index: ObjectIndex) -> list[Finding]:
    relief: list[Ref] = []
    for pt in pts:
        for rx in RELIEF_RE:
            for m in rx.finditer(pt.text):
                lo, hi = _num(m.group("lo")), _num(m.group("hi"))
                if lo is not None and hi is not None:
                    relief.append(Ref(page=pt.page, quote=_quote(pt.text, m.group()), object="site",
                                      value=[min(lo, hi), max(lo, hi)], unit="m"))
    if not relief:
        return []
    lo = min(r.value[0] for r in relief)
    hi = max(r.value[1] for r in relief)
    outside: list[Ref] = []
    for pt in pts:
        for rx in Z_RE:
            for m in rx.finditer(pt.text):
                z = _num(m.group("z"))
                obj = _object(pt, index, m.start(), m.end())
                if z is None or obj is None:
                    continue
                if not lo - ELEVATION_SLACK_M <= z <= hi + ELEVATION_SLACK_M:
                    outside.append(Ref(page=pt.page, quote=_quote(pt.text, m.group()), object=obj, value=z, unit="m"))
    if not outside:
        return []
    return [_finding(DiscrepancyType.VALUE_CROSS_SECTION_MISMATCH, "absolute_elevation_m", "site", outside + relief,
                     confidence="needs_expert",
                     note=f"elevation 0.000 outside the relief {lo:g}–{hi:g} m (± {ELEVATION_SLACK_M:g})")]


VOLUME_METHOD_TOL = 0.005  # V vs S x clear height
MIN_STOREY_M = 2.8  # average storey height by volume below this is implausible; tuned on v4 dev
_NUM_M = re.compile(rf"(?P<num>{NUMBER_RE.pattern})\s*м(?![^\W\d_])", re.IGNORECASE)
_SENTENCE_END = re.compile(r"\.\s+(?=[A-ZА-ЯЁӘҒҚҢӨҰҮҺІ][a-zа-яёәғқңөұүһі])")


def _heights(pts: list[PageText], index: ObjectIndex, name: str) -> dict[str, list[Ref]]:
    """object -> heights in metres stated right after a parameter mention ("в чистоте … 2,6м")."""
    param = load_parameters()[name]
    out: dict[str, list[Ref]] = {}
    for pt in pts:
        for m in param.mention_re.finditer(pt.text):
            tail = pt.text[m.end(): m.end() + 80]
            if end := _SENTENCE_END.search(tail):
                tail = tail[: end.start()]
            h = _NUM_M.search(tail)
            obj = _object(pt, index, m.start(), m.end())
            if h is None or obj is None or (value := _num(h.group("num"))) is None or not 1.5 <= value <= 20:
                continue
            quote = _quote(pt.text, pt.text[m.start(): m.end() + h.end()])
            out.setdefault(obj, []).append(Ref(page=pt.page, quote=quote, object=obj, value=value, unit="m"))
    return out


def check_volume_method(pts: list[PageText], index: ObjectIndex, mentions: list[Mention],
                        floors: dict[str, int]) -> list[Finding]:
    by_obj: dict[str, dict[str, list[Mention]]] = {}
    for m in mentions:
        if m.object and m.field in ("construction_volume_m3", "building_area_m2"):
            by_obj.setdefault(m.object, {}).setdefault(m.field, []).append(m)
    clear = _heights(pts, index, "clear_height")
    out = []
    for obj, fields in by_obj.items():
        volumes, areas = fields.get("construction_volume_m3", []), fields.get("building_area_m2", [])
        hit = next(([Ref(page=v.page, quote=v.quote, object=obj, value=v.value, unit="m3",
                         derived=f"{v.value:g} = {s.value:g} x {h.value:g}"),
                     Ref(page=s.page, quote=s.quote, object=obj, value=s.value, unit="m2"), h]
                    for v in volumes for s in areas for h in clear.get(obj, [])
                    if abs(s.value * h.value - v.value) <= VOLUME_METHOD_TOL * v.value), None)
        if hit is None and floors.get(obj) and volumes and areas:
            v, s = min(volumes, key=lambda m: m.value), max(areas, key=lambda m: m.value)
            if v.value / (s.value * floors[obj]) < MIN_STOREY_M:
                hit = [Ref(page=v.page, quote=v.quote, object=obj, value=v.value, unit="m3",
                           derived=f"{v.value:g} / ({s.value:g} x {floors[obj]}) < {MIN_STOREY_M:g} m"),
                       Ref(page=s.page, quote=s.quote, object=obj, value=s.value, unit="m2")]
        if hit:
            out.append(_finding(DiscrepancyType.TEP_CALCULATION_METHOD, "construction_volume_m3", obj, hit,
                                confidence="needs_expert", note=hit[0].derived or ""))
    return out


def check_table_labels(pages: list[Page], pts: list[PageText], index: ObjectIndex) -> list[Finding]:
    """A one-row table inside the section of building X whose row names another building (or an unknown one)."""
    out = []
    carried = [None] + [pt.ctx_after for pt in pts[:-1]]
    names = index.by_id()
    for page, pt, car in zip(pages, pts, carried, strict=True):
        for table in page.tables:
            section = pt.context_above(table.top, car)
            if section is None:
                continue
            rows = [r for r in table.rows[1:] if any(_num(c) is not None for c in r if c)]
            labels = [next((c for c in r if c and re.search(r"[^\W\d_]", c)), "") for r in rows]
            if len(rows) != 1 or not labels[0]:
                continue  # summary tables (several objects) and unlabelled rows are not checked
            named = index.mentioned(labels[0])
            if section in named or not (named or OBJECT_NOUN_RE.search(labels[0])):
                continue
            quote = _quote(pt.text, " ".join(c for c in rows[0] if c), labels[0])
            out.append(_finding(DiscrepancyType.COPY_PASTE_LABEL, "object_label", section,
                                [Ref(page=pt.page, quote=quote, object=section, value=labels[0])],
                                note=f"table in the section of {names[section].name!r} is labelled {labels[0]!r}"))
    return out


WIDTH_TOL = 0.01
# a phrase ends at a full stop before a capitalised word, or at ";" ("кл. В 7.5" does not end it: "В" + space)
_PHRASE_END = re.compile(_SENTENCE_END.pattern + "|;")


def _phrase(text: str, start: int, end: int) -> tuple[int, int]:
    s = 0
    for m in _PHRASE_END.finditer(text, 0, start):
        s = m.end()
    e = _PHRASE_END.search(text, end)
    return s, e.start() if e else len(text)


def check_parameters(pts: list[PageText], index: ObjectIndex) -> list[Finding]:
    """Per building, its statements of a parameter together with the general ("all") ones: different materials
    or widths -> contradiction. The finding belongs to "all" when a general statement takes part."""
    out = []
    for name, param in load_parameters().items():
        if not param.materials:
            continue
        by_obj: dict[str, list[tuple[Ref, str | None, float | None]]] = {}
        for pt in pts:
            for m in param.mention_re.finditer(pt.text):
                s, e = _phrase(pt.text, m.start(), m.end())
                phrase = pt.text[s:e].strip()
                material = param.material_in(phrase)
                width = width_mm(phrase) if param.has_width else None
                if material is None and width is None:
                    continue
                obj = resolve(pt, index, m.start(), m.end())[0] or "all"
                value = ", ".join(x for x in (material, f"{width:g} мм" if width else None) if x)
                ref = Ref(page=pt.page, quote=_quote(pt.text, phrase), object=obj, value=value)
                by_obj.setdefault(obj, []).append((ref, material, width))
        general = by_obj.get("all", [])
        groups = [items + general for obj, items in by_obj.items() if obj != "all"] or [general]
        seen = set()
        for group in groups:
            materials = {mat for _, mat, _ in group if mat}
            widths = sorted(w for _, _, w in group if w)
            if len(materials) <= 1 and not (widths and widths[-1] - widths[0] > WIDTH_TOL * widths[-1]):
                continue
            scope = "all" if any(r.object == "all" for r, _, _ in group) else group[0][0].object
            if scope in seen:
                continue
            seen.add(scope)
            out.append(_finding(DiscrepancyType.PARAMETER_CONTRADICTION, name, scope, [r for r, _, _ in group],
                                note=f"{name}: " + "; ".join(str(r.value) for r, _, _ in group)))
    return out
