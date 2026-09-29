"""Number/unit normalization for real documents (synthetic inputs only)."""

from __future__ import annotations

import pytest

from src.ingestion.common.numbers import find_numbers, normalize_unit, number_readings, parse_number


@pytest.mark.parametrize("text,value", [
    ("1 247,79", 1247.79), ("1\u00a0247,79", 1247.79), ("1\u202f247,79", 1247.79), ("1247,79", 1247.79),
    ("4963.84", 4963.84), ("1548217", 1548217), ("12 345 678", 12345678), ("0,292", 0.292),
    ("1,234.56", 1234.56), ("1.234,56", 1234.56), ("1.234.567", 1234567), ("-12,5", -12.5),
])
def test_parse_number(text, value):
    assert parse_number(text) == pytest.approx(value)


def test_ambiguity():
    assert number_readings("1,234") == (1.234, 1234.0)
    assert number_readings("4.963") == (4.963, 4963.0)
    assert len(number_readings("0,125")) == 1  # a leading zero can only be decimal
    assert len(number_readings("12,50")) == 1
    assert number_readings("abc") == () and parse_number("1,2,3") is None


def test_find_numbers_in_text():
    nums = find_numbers("размерами 8,5х24,0м, объем 1 247,79 м3 и 4963.84; ряд 199,50 518,70 113,28")
    assert [n.value for n in nums] == [8.5, 24.0, 1247.79, 4963.84, 199.5, 518.7, 113.28]
    assert not any(n.ambiguous for n in nums)


@pytest.mark.parametrize("text,unit", [
    ("м2", "m2"), ("м²", "m2"), ("кв.м", "m2"), ("кв. м.", "m2"), ("м.кв.", "m2"), ("m2", "m2"),
    ("м3", "m3"), ("м³", "m3"), ("куб.м", "m3"), ("куб. м", "m3"), ("M3", "m3"),
    ("м", None), ("мм", None), ("т", None), ("га", None),
])
def test_normalize_unit(text, unit):
    assert normalize_unit(text) == unit


# ------------------------------------------------------------ table headers
from src.ingestion.real import glue_wrapped, merge_split_header  # noqa: E402


@pytest.mark.parametrize("cell,expected", [
    ("Этажнос\nть", "Этажность"),
    ("Общая\nплощад\nь", "Общая площадь"),
    ("Строительный\nобъем", "Строительный объем"),
    ("Типы\nгрунтовых\nусловий по\nсейсмически\nм свойствам", "Типы грунтовых условий по сейсмическим свойствам"),
    ("Ед.\nизм.", "Ед. изм."),
    ("подзем-\nный", "подземный"),
    ("Площадь\nв осях", "Площадь в осях"),
    ("Количество\nшт", "Количество шт"),
    (None, ""),
])
def test_glue_wrapped(cell, expected):
    assert glue_wrapped(cell) == expected


def test_merge_split_header():
    assert merge_split_header(["Наименование", "Этажнос", "ть", "Площадь"]) == \
        ["Наименование", "Этажность", "Этажность", "Площадь"]
    assert merge_split_header(["Длина,", "м"]) == ["Длина,", "м"]
