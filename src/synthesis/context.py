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
