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


# Number styles seen in real documents (profile v2): '1 247,79', '1247,79', '4963.84', NBSP-grouped.
NUMBER_STYLES = ("space_comma", "plain_comma", "plain_dot", "nbsp_comma")
NUMBER_STYLE_WEIGHTS = (0.4, 0.3, 0.2, 0.1)


def fmt_styled(value: float | int, decimals: int, style: str) -> str:
    if isinstance(value, int):
        return str(value)
    s = f"{value:,.{decimals}f}"  # '12,345.67'
    if style == "space_comma":
        return s.replace(",", " ").replace(".", ",")
    if style == "nbsp_comma":
        return s.replace(",", " ").replace(".", ",")
    s = s.replace(",", "")
    return s.replace(".", ",") if style == "plain_comma" else s


def split_header_word(text: str, rng) -> str:
    """Break one long word of a header cell without a hyphen, as narrow Word columns do ('Этажнос\\nть')."""
    words = text.split(" ")
    long = [i for i, w in enumerate(words) if len(w) >= 7 and w.isalpha()]
    if not long:
        return text
    i = rng.choice(long)
    tail = rng.choice((1, 2, 2, 3))
    words[i] = words[i][:-tail] + "\n" + words[i][-tail:]
    return " ".join(words)
