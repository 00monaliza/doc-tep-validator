"""Parsing numbers and units as they appear in real RU/KZ project documents.

Real documents mix formats within one file: ``4963.84``, ``518,70``,
``1548217``, ``1 247,79`` (regular, NBSP or narrow NBSP as thousands
separator). A lone separator followed by exactly three digits (``1,234``,
``4.963``) is genuinely ambiguous: in RU/KZ practice it is usually a decimal
comma, but it can be a thousands separator. ``parse_number`` returns the most
likely reading and ``number_readings`` lists every plausible one so callers can
flag ambiguity instead of silently guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SPACES = "\u00a0\u202f\u2009 "  # NBSP, narrow NBSP, thin space, space
_SP = f"[{SPACES}]"
# 1 247,79 | 1247,79 | 4963.84 | 1,234.56 | 1.234.567 | 1548217 | -12,5;
# a digit right after м/m is a unit exponent ('м3'), not a number.
NUMBER_RE = re.compile(
    rf"(?<![\d.,])(?<![мМmM])-?(?:\d{{1,3}}(?:{_SP}\d{{3}})+|\d{{1,3}}(?:[.,]\d{{3}}){{2,}}|\d+)(?:[.,]\d+)?(?![\d])"
)


@dataclass(frozen=True)
class ParsedNumber:
    text: str
    value: float
    readings: tuple[float, ...]  # all plausible values, most likely first
    start: int = 0
    end: int = 0

    @property
    def ambiguous(self) -> bool:
        return len(self.readings) > 1


def number_readings(text: str) -> tuple[float, ...]:
    """All plausible numeric values of a number token, most likely first.

    ``()`` if the token is not a number.
    """
    s = text.strip()
    for ch in SPACES:
        s = s.replace(ch, "")
    if not re.fullmatch(r"-?[\d.,]*\d", s) or not re.search(r"\d", s):
        return ()
    commas, dots = s.count(","), s.count(".")
    if commas and dots:  # both: the last one is the decimal separator
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        thou = "." if dec == "," else ","
        if s.count(dec) > 1:
            return ()
        return (float(s.replace(thou, "").replace(dec, ".")),)
    sep = "," if commas else "." if dots else ""
    if not sep:
        return (float(s),)
    parts = s.split(sep)
    if len(parts) > 2:  # 1.234.567: only thousands grouping makes sense
        if all(len(p) == 3 for p in parts[1:]):
            return (float("".join(parts)),)
        return ()
    head, tail = parts
    decimal = float(f"{head}.{tail}")
    if len(tail) == 3 and head.lstrip("-") not in ("", "0"):
        return (decimal, float(head + tail))  # 1,234: decimal first (RU/KZ convention)
    return (decimal,)


def parse_number(text: str) -> float | None:
    readings = number_readings(text)
    return readings[0] if readings else None


def find_numbers(text: str) -> list[ParsedNumber]:
    """Every number token in free text or a table cell, left to right."""
    out = []
    for m in NUMBER_RE.finditer(text):
        readings = number_readings(m.group())
        if readings:
            out.append(ParsedNumber(m.group(), readings[0], readings, m.start(), m.end()))
    return out


# ------------------------------------------------------------------ units
_UNIT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("m2", re.compile(r"^(?:[мm]\.?\s*[2²]|кв\.?\s*[мm]\.?|[мm]\.?\s*кв\.?|sq\.?\s*m)$", re.IGNORECASE)),
    ("m3", re.compile(r"^(?:[мm]\.?\s*[3³]|куб\.?\s*[мm]\.?|[мm]\.?\s*куб\.?|cu\.?\s*m)$", re.IGNORECASE)),
)
# the same forms, searchable inside text (followed by a non-letter)
UNIT_IN_TEXT_RE = re.compile(
    r"(?<![^\W\d_])(?:(?P<m2>[мm]\.?\s?[2²]|кв\.\s?[мm]\.?|[мm]\.?\s?кв\.?)|(?P<m3>[мm]\.?\s?[3³]|куб\.\s?[мm]\.?|[мm]\.?\s?куб\.?))"
    r"(?![^\W\d_]|\d)",
    re.IGNORECASE,
)


def normalize_unit(text: str) -> str | None:
    """'м2' | 'м²' | 'кв.м' | 'м3' | 'м³' | 'куб.м' ... -> 'm2' | 'm3'; None if unknown."""
    s = text.strip().replace(" ", " ")
    for canon, pattern in _UNIT_PATTERNS:
        if pattern.match(s):
            return canon
    return None
