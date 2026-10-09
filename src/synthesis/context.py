"""Per-set context handed to language templates."""

from __future__ import annotations

import random
from dataclasses import dataclass

from src.ner.common.taxonomy import Section
from src.synthesis.formatting import NUMBER_STYLE_WEIGHTS, NUMBER_STYLES, fmt_num, fmt_styled
from src.synthesis.values import PzPlan, SetValues

# Synthetic normative codes for local-estimate lines (placeholders, not real СН РК codes).
NORM_CODES = {
    "concrete_b25_foundation_m3": "Е06-01-001-01",
    "concrete_b30_frame_m3": "Е06-01-026-02",
    "rebar_a500c_t": "Е06-01-015-05",
    "brick_masonry_m3": "Е08-02-001-03",
    "steel_structures_t": "Е09-03-002-01",
}
OCR_NOISE_RATE = 0.2  # share of held-out labels with an OCR-like defect
# unit text used by the templates -> canonical unit of the held-out vocabulary
UNIT_CANON = {"м²": "m2", "м³": "m3", "этаж": "floor", "эт.": "floor", "қабат": "floor",
              "тыс. тенге": "kKZT", "мың теңге": "kKZT", "мес.": "month", "ай": "month"}
_OCR_SWAPS = {"щ": "ш", "ь": "ъ", "о": "o", "а": "a", "е": "e", "р": "p", "с": "c", "і": "i", "ы": "ьі"}


def ocr_noise(text: str, rng: random.Random) -> str:
    """One OCR-like defect: a look-alike letter (Cyrillic -> Latin), a lost space or a word split by a space."""
    op = rng.choice(("swap", "glue", "split"))
    if op == "swap":
        spots = [i for i, ch in enumerate(text) if ch.lower() in _OCR_SWAPS]
        if spots:
            i = rng.choice(spots)
            rep = _OCR_SWAPS[text[i].lower()]
            return text[:i] + (rep.upper() if text[i].isupper() else rep) + text[i + 1:]
    if op == "glue" and " " in text:
        i = rng.choice([i for i, ch in enumerate(text) if ch == " "])
        return text[:i] + text[i + 1:]
    words = text.split(" ")
    long = [i for i, w in enumerate(words) if len(w) >= 6]
    if not long:
        return text
    k = rng.choice(long)
    cut = rng.randint(2, len(words[k]) - 2)
    words[k] = words[k][:cut] + " " + words[k][cut:]
    return " ".join(words)


@dataclass
class Meta:
    object_name: str
    city: str
    address: str
    customer: str
    designer: str
    chief_engineer: str
    project_code: str
    year: int


@dataclass
class Ctx:
    lang: str
    v: SetValues
    meta: Meta
    rng: random.Random  # phrasing variants only; numbers are fixed in `v`
    plan: PzPlan | None = None  # profile v2: several buildings in the ПЗ
    vrng: random.Random | None = None  # profile v2 surface variation (labels, formats, column order)
    heldout: dict | None = None  # profile v3: held-out wording (data/heldout.py), one half of one language
    hrng: random.Random | None = None  # profile v3 choices; a separate stream keeps v2 draws as they are

    @property
    def v2(self) -> bool:
        return self.plan is not None

    def style(self) -> str:
        """A number style for one table or sentence (always the v1 style in profile v1)."""
        if self.vrng is None:
            return "space_comma"
        return self.vrng.choices(NUMBER_STYLES, NUMBER_STYLE_WEIGHTS)[0]

    def get(self, section: Section, fld: str):
        return self.v.tep[section][fld]

    def fmt(self, section: Section, fld: str, style: str = "space_comma") -> str:
        """Format a TEP value with the decimals the documents use for its unit."""
        value = self.v.tep[section][fld]
        if isinstance(value, int):
            return str(value)
        head = fld.split(".")[0]  # "local_cost_tg.rebar_a500c_t" is money, not tonnes
        if fld.endswith("_ktg"):
            decimals = 3
        elif head.endswith("_tg") or fld.endswith("_tg"):
            decimals = 2
        elif fld.endswith("_pct"):
            decimals = 1
        elif fld.endswith("_t"):
            decimals = 3
        else:
            decimals = 2
        return fmt_num(value, decimals) if style == "space_comma" else fmt_styled(value, decimals, style)

    def pick(self, *variants: str) -> str:
        return self.rng.choice(variants)

    def held_label(self, fld: str) -> str | None:
        """A held-out label for a TEP field (sometimes with an OCR defect), or None outside profile v3."""
        variants = self.heldout["labels"].get(fld) if self.heldout else None
        if not variants:
            return None
        label = self.hrng.choice(variants)
        return ocr_noise(label, self.hrng) if self.hrng.random() < OCR_NOISE_RATE else label

    def held_unit(self, unit: str) -> str | None:
        """A held-out spelling of a template unit ('м²', 'эт.', 'мес.' …), or None."""
        variants = self.heldout["units"].get(UNIT_CANON.get(unit, "")) if self.heldout else None
        return self.hrng.choice(variants) if variants else None

    def held_template(self, name: str) -> str | None:
        variants = self.heldout["templates"].get(name) if self.heldout else None
        return self.hrng.choice(variants) if variants else None
