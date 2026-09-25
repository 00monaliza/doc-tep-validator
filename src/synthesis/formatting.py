"""Number formatting as used in RU/KZ project documentation: '12 345,67'."""

from __future__ import annotations


def fmt_num(value: float | int, decimals: int = 2) -> str:
    s = f"{value:,.{decimals}f}"  # '12,345.67'
    return s.replace(",", " ").replace(".", ",")


def parse_num(text: str) -> float:
    """Inverse of fmt_num (tolerates NBSP / narrow NBSP thousands separators)."""
    for ch in (" ", " ", " "):
        text = text.replace(ch, "")
    return float(text.replace(",", "."))
