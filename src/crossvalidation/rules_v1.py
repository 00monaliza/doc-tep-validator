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

from src.crossvalidation.objects import ObjectIndex, PageText, resolve
from src.crossvalidation.rules import _finding, _quote
from src.evaluation.schema import Finding, Ref
from src.ingestion.common.numbers import NUMBER_RE, number_readings
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
