"""Rules v0 on small hand-made PDFs: fire resistance, both word orders of TEP repeats, bare volumes."""

from __future__ import annotations

from pathlib import Path

import pytest
from fpdf import FPDF

from src.crossvalidation.rules import run_rules
from src.ingestion.real import load_pages
from src.synthesis.render import FONT_REGULAR


def make_pdf(tmp_path: Path, pages: list[list[str]]) -> list:
    pdf = FPDF()
    pdf.add_font("DejaVu", fname=str(FONT_REGULAR))
    pdf.set_font("DejaVu", size=11)
    for lines in pages:
        pdf.add_page()
        for line in lines:
            pdf.multi_cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "doc.pdf"
    pdf.output(str(path))
    return load_pages(path)


def findings(pages, ftype: str, field: str | None = None) -> list:
    return [f for f in run_rules(pages).findings if f.type.value == ftype and (field is None or f.field == field)]


# ------------------------------------------------------------------ fire resistance
def test_fire_resistance_contradiction_ru(tmp_path):
    pages = make_pdf(tmp_path, [
        ["1. Здание котельной", "Уровень ответственности — II. Степень огнестойкости — II."],
        ["Противопожарные мероприятия", "Для здания котельной принята III степень огнестойкости."],
    ])
    (f,) = findings(pages, "PARAMETER_CONTRADICTION", "fire_resistance")
    assert sorted({r.value for r in f.refs}) == ["II", "III"]


def test_fire_resistance_cyrillic_numerals_kz(tmp_path):
    """Kazakh texts type Roman numerals with Cyrillic 'І'; 'ІІ' and 'II' are the same degree."""
    same = make_pdf(tmp_path, [["1. Мектеп ғимараты", "Отқа төзімділік дәрежесі — ІІ."],
                               ["Өртке қарсы іс-шаралар", "Мектеп ғимаратының отқа төзімділік дәрежесі — II."]])
    assert findings(same, "PARAMETER_CONTRADICTION", "fire_resistance") == []
    diff = make_pdf(tmp_path, [["1. Мектеп ғимараты", "Отқа төзімділік дәрежесі — ІІ."],
                               ["Өртке қарсы іс-шаралар", "Мектеп ғимаратының отқа төзімділік дәрежесі — ІV."]])
    (f,) = findings(diff, "PARAMETER_CONTRADICTION", "fire_resistance")
    assert sorted({r.value for r in f.refs}) == ["II", "IV"]


def test_fire_resistance_of_two_buildings_is_not_a_contradiction(tmp_path):
    pages = make_pdf(tmp_path, [["1. Здание школы", "Степень огнестойкости здания — II."],
                                ["2. Здание котельной", "Степень огнестойкости здания — III."]])
    assert findings(pages, "PARAMETER_CONTRADICTION", "fire_resistance") == []


# ------------------------------------------------------------------ TEP repeats
def test_kz_number_first_repeat(tmp_path):
    pages = make_pdf(tmp_path, [
        ["1. Мектеп ғимараты", "Мектеп ғимаратының құрылыс көлемі 1 000,00 м³ құрайды."],
        ["Инженерлік желілер", "Мектеп ғимаратының 1 200,00 м³ құрылыс көлемі жобада қабылданған."],
    ])
    (f,) = findings(pages, "TEP_CROSS_SECTION_MISMATCH", "construction_volume_m3")
    assert sorted(r.value for r in f.refs) == [1000.0, 1200.0]


@pytest.mark.parametrize(("bare", "expected"), [
    ("Объём котельной равен — 1 000,00 м³.", 1),  # names the building: its construction volume
    ("Объём резервуара равен — 50,00 м³.", 0),  # a tank is not a building of the document
])
def test_bare_volume_needs_a_building_name(tmp_path, bare, expected):
    pages = make_pdf(tmp_path, [["1. Здание котельной", "Строительный объём здания котельной составляет 900,00 м³."],
                                ["Инженерные сети", bare]])
    assert len(findings(pages, "TEP_CROSS_SECTION_MISMATCH", "construction_volume_m3")) == expected
