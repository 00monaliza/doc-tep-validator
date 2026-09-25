"""Language and section detection for an uploaded document.

Language: share of Kazakh-specific letters among Cyrillic letters.
Section: title keywords on the first page (RU/KZ), then the document code
suffix (…-ПЗ / …-ТЖ etc.), then table signatures as a fallback.
"""

from __future__ import annotations

import re

from src.ingestion.common.layout import Layout
from src.ner.common.taxonomy import Section

KZ_LETTERS = set("ӘәҒғҚқҢңӨөҰұҮүҺһІі")
KZ_SHARE_THRESHOLD = 0.01  # Kazakh prose has ~5–8 % of these letters

TITLE_PATTERNS: dict[Section, tuple[str, ...]] = {
    Section.PZ: (r"пояснительн\w* записк", r"түсіндірме жазба"),
    Section.AR: (r"архитектурн\w* решени", r"сәулет шешімдер"),
    Section.KR: (r"конструктивн\w* решени", r"конструктивтік шешімдер"),
    Section.SMETA: (r"сметн\w* документац", r"сметалық құжаттама", r"сводн\w* сметн\w* расч",
                    r"жиынтық сметалық есеп", r"локальн\w* смет", r"жергілікті смета"),
}
CODE_SUFFIX: dict[str, Section] = {
    "ПЗ": Section.PZ, "ТЖ": Section.PZ, "АР": Section.AR, "СШ": Section.AR,
    "КР": Section.KR, "КШ": Section.KR, "СД": Section.SMETA, "СҚ": Section.SMETA, "СМ": Section.SMETA,
}
CODE_RE = re.compile(r"\b\d{2,}[-–]\d{4}[-–](" + "|".join(CODE_SUFFIX) + r")\b")


KZ_WORDS = {"және", "мен", "бойынша", "үшін", "жылғы", "құрайды", "сәйкес", "арналған", "бұл", "оның", "барлығы"}
RU_WORDS = {"и", "в", "на", "по", "для", "с", "из", "составляет", "согласно", "не", "итого", "всего"}
MIN_VOTES = 5


def detect_language(text: str) -> str:
    """Function-word vote first (robust to OCR noise: Tesseract 'kaz' sprinkles Kazakh
    letters into Russian text), share of Kazakh letters as a fallback for short texts."""
    words = re.findall(r"[^\W\d_]+", text.lower())
    kz_votes, ru_votes = sum(w in KZ_WORDS for w in words), sum(w in RU_WORDS for w in words)
    if kz_votes + ru_votes >= MIN_VOTES:
        return "kz" if kz_votes > ru_votes else "ru"
    cyr = [c for c in text if "Ѐ" <= c <= "ӿ"]
    if not cyr:
        return "ru"
    return "kz" if sum(c in KZ_LETTERS for c in cyr) / len(cyr) >= KZ_SHARE_THRESHOLD else "ru"


def detect_section(layout: Layout) -> tuple[Section | None, str]:
    """Return (section, how it was decided)."""
    first_page = " ".join(ln.text for ln in layout.lines if ln.page == 1).lower()
    hits = {sec: min((m.start() for p in pats if (m := re.search(p, first_page))), default=None)
            for sec, pats in TITLE_PATTERNS.items()}
    hits = {s: pos for s, pos in hits.items() if pos is not None}
    if hits:
        return min(hits, key=hits.get), "title"
    if m := CODE_RE.search(layout.text()):
        return CODE_SUFFIX[m.group(1)], "document code"
    headers = " ".join(" ".join(t.header) for t in layout.tables).lower()
    if re.search(r"цена|бағасы", headers):
        return Section.SMETA, "table signature"
    if re.search(r"№ пом|үй-жай №", headers):
        return Section.AR, "table signature"
    return None, "unknown"
