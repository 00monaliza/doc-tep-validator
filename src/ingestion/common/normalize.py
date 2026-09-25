"""Unit normalisation for the OCR path: restore 'м²' / 'м³' after Tesseract.

Tesseract's rus/kaz models have no superscripts, and on noisy scans the
exponent comes out as '2', '3', 'з', '?', '*' or disappears entirely. Observed
on data/synthetic scans (see tests/test_normalize.py for the real OCR lines):

    'площадь здания 1 247,79 м2,'       'объём — 8 833,38 мз.'
    'жалпы ауданы 2 118,34 м? деп'      'кірпіштен қалау м2 7 259,45'  (really м³!)

The OCR digit is unreliable (the last example is a volume read as 'м2'), so the
exponent is resolved from the nearest area/volume keyword in the same line,
preceding keywords first (both languages put the label before the value). The
OCR digit is only a fallback when the line has no keyword.

Tokens that must not change: 'мм' (mm), 'ММ' (Kazakh abbreviation of ГУ),
'М/6' (misread W6), 'М200' (concrete grade), plain metres like '3,6 м.'.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LETTER = r"[^\W\d_]"
# м + optional exponent-like glyph; not glued to other letters/digits.
UNIT_RE = re.compile(rf"(?<!{LETTER})(?P<m>[мМm])(?P<exp>[2²3³зЗ?*])?(?![^\W_])")

AREA_KEYWORDS = ("площад", "аудан")
VOLUME_KEYWORDS = ("объём", "объем", "көлем", "бетон", "кладк", "қалау", "кірпіш", "кирпич", "подземн", "жерасты")
KEYWORD_RE = re.compile("|".join(AREA_KEYWORDS + VOLUME_KEYWORDS), re.IGNORECASE)

EXP_HINT = {"2": "²", "²": "²", "3": "³", "³": "³", "з": "³", "З": "³"}
NUMBER_BEFORE = re.compile(r"\d[\s|]{0,3}$")
NUMBER_AFTER = re.compile(r"^[\s|]{0,3}\d")


@dataclass(frozen=True)
class UnitFix:
    line: int
    original: str
    replacement: str  # equals original when unresolved
    reason: str  # context | context_overrides_ocr | ocr_hint | unresolved


def _context_exponent(line: str, pos: int) -> str | None:
    """Exponent implied by the nearest keyword, preferring ones before `pos`."""
    before = [m for m in KEYWORD_RE.finditer(line) if m.start() < pos]
    after = [m for m in KEYWORD_RE.finditer(line) if m.start() >= pos]
    kw = before[-1] if before else (after[0] if after else None)
    if kw is None:
        return None
    return "²" if kw.group(0).lower().startswith(AREA_KEYWORDS) else "³"


def _normalize_line(line: str, line_no: int, fixes: list[UnitFix]) -> str:
    out, last = [], 0
    for m in UNIT_RE.finditer(line):
        letter, exp = m.group("m"), m.group("exp")
        if exp is None:
            # A bare 'м' is usually metres; upgrade it only next to a number in a keyword context.
            # (Uppercase 'М' qualifies too: OCR capitalises units in table cells; 'М/6' has no number next to it.)
            if letter == "m":
                continue
            near_number = NUMBER_BEFORE.search(line[: m.start()]) or NUMBER_AFTER.search(line[m.end():])
            ctx = _context_exponent(line, m.start()) if near_number else None
            if ctx is None:
                continue
            new, reason = "м" + ctx, "context"
        else:
            hint, ctx = EXP_HINT.get(exp), _context_exponent(line, m.start())
            if ctx is not None:
                new = "м" + ctx
                reason = "context_overrides_ocr" if hint and hint != ctx else "context"
            elif hint is not None:
                new, reason = "м" + hint, "ocr_hint"
            else:  # '?' or '*' with no keyword: leave as is, report
                fixes.append(UnitFix(line_no, m.group(0), m.group(0), "unresolved"))
                continue
        fixes.append(UnitFix(line_no, m.group(0), new, reason))
        out.append(line[last:m.start()])
        out.append(new)
        last = m.end()
    out.append(line[last:])
    return "".join(out)


def normalize_units(text: str) -> tuple[str, list[UnitFix]]:
    """Return text with м²/м³ restored and a log of every decision made."""
    fixes: list[UnitFix] = []
    lines = [_normalize_line(line, i, fixes) for i, line in enumerate(text.split("\n"))]
    return "\n".join(lines), fixes
