from __future__ import annotations

from src.crossvalidation import rules_v1
from src.crossvalidation.objects import page_texts
from src.crossvalidation.rules import Mention, run_rules
from src.crossvalidation.rules_v1 import (
    check_elevation,
    check_parameters,
    check_table_labels,
    check_volume_method,
)
from src.ingestion.real import Page, PageTable, TextLine
from src.ner.common.tep_baseline import object_index


def _page(no: int, lines: list[str], tables: list[PageTable] = ()) -> Page:
    text_lines = [TextLine(t, 20.0 * i) for i, t in enumerate(lines)]
    return Page(no, "\n".join(lines), text_lines, list(tables))


def _pages(*pages: list[str]) -> list[Page]:
    return [_page(i, lines) for i, lines in enumerate(pages, start=1)]


def _ctx(pages):
    index = object_index(pages)
    return index, page_texts(pages, index)


TWO_BUILDINGS = ["5. Объёмно-планировочные решения", "5.1 Здание офиса", "5.2 Здание цеха"]


def test_elevation_outside_relief():
    pages = _pages(["Рельеф площадки спокойный, абсолютные отметки поверхности изменяются от 314,75 м до 315,04 м."],
                   ["5.1 Здание офиса",
                    "Относительная отметка 0,000 соответствует абсолютной отметке - 489,79."])
    index, pts = _ctx(pages)
    found = check_elevation(pts, index)
    assert len(found) == 1 and found[0].object == "site" and found[0].field == "absolute_elevation_m"
    assert 489.79 in [r.value for r in found[0].refs]


def test_elevation_inside_relief_is_fine():
    pages = _pages(["Абсолютные отметки поверхности земли на участке — от 314,75 м до 315,04 м."],
                   ["5.1 Здание офиса", "Относительная отметка 0,000 соответствует абсолютной отметке 315,30 м."])
    index, pts = _ctx(pages)
    assert check_elevation(pts, index) == []


def test_relief_sentence_is_not_building_elevation():
    pages = _pages(["5.1 Здание офиса",
                    "Абсолютные отметки поверхности изменяются от 314,75 м до 315,04 м."])
    index, pts = _ctx(pages)
    assert check_elevation(pts, index) == []  # no building elevation at all: nothing to compare


def test_kazakh_elevation_and_relief():
    pages = _pages(["Учаскедегі жер бетінің абсолюттік белгілері 314,75 м-ден 315,04 м-ге дейін."],
                   ["5.1 Қазандық ғимараты", "Салыстырмалы 0,000 белгісі 512,40 м абсолюттік белгіге сәйкес келеді."])
    index, pts = _ctx(pages)
    assert len(check_elevation(pts, index)) == 1


def _m(obj, fld, value, page=1, quote="q"):
    return Mention(obj, fld, value, page, quote, "table", "test")


def test_volume_is_area_times_clear_height():
    pages = _pages(["5.2 Здание цеха", "Высота помещений в чистоте от пола до низа потолка 2,6м"])
    index, pts = _ctx(pages)
    ceh = index.objects[0].id
    mentions = [_m(ceh, "construction_volume_m3", 518.7), _m(ceh, "building_area_m2", 199.5)]
    found = check_volume_method(pts, index, mentions, {})
    assert len(found) == 1 and found[0].object == ceh and found[0].type.value == "TEP_CALCULATION_METHOD"


def test_outer_volume_is_fine():
    pages = _pages(["5.2 Здание цеха",
                    "Высота этажа — 3,3 м, высота помещений в чистоте от пола до низа потолка 2,9 м."])
    index, pts = _ctx(pages)
    ceh = index.objects[0].id
    mentions = [_m(ceh, "construction_volume_m3", 760.0), _m(ceh, "building_area_m2", 199.5)]
    assert check_volume_method(pts, index, mentions, {ceh: 1}) == []


def test_low_average_storey_height():
    pages = _pages(["5.2 Здание цеха", "Описание."])
    index, pts = _ctx(pages)
    ceh = index.objects[0].id
    mentions = [_m(ceh, "construction_volume_m3", 1000.0), _m(ceh, "building_area_m2", 200.0)]
    assert len(check_volume_method(pts, index, mentions, {ceh: 2})) == 1  # 1000 / (200 x 2) = 2,5 m


HEADER = ["Наименование", "Площадь застройки", "Строительный объём"]


def _section_pages(heading: str, rows: list[list[str]]) -> list[Page]:
    """Page 1: the office section; page 2: `heading` and a table right below it (top 40 > heading top 0)."""
    lines = [heading, "Объёмно-планировочные показатели"] + [" ".join(r) for r in rows]
    table = PageTable(rows, (0, 40.0, 500, 40.0 + 20 * len(rows)), rows[0])
    return [_page(1, ["5. Решения", "5.1 Здание офиса", "Текст."]), _page(2, lines, [table])]


def test_wrong_building_in_table():
    pages = _section_pages("5.2 Здание цеха", [HEADER, ["Здание офиса", "199,50", "518,70"]])
    index, pts = _ctx(pages)
    found = check_table_labels(pages, pts, index)
    assert len(found) == 1 and found[0].field == "object_label"
    assert index.by_id()[found[0].object].name == "Здание цеха"


def test_own_building_in_table_is_fine():
    pages = _section_pages("5.2 Здание цеха", [HEADER, ["Здание цеха", "199,50", "518,70"]])
    index, pts = _ctx(pages)
    assert check_table_labels(pages, pts, index) == []


def test_summary_table_is_not_a_label():
    rows = [HEADER, ["Здание офиса", "312,91", "3116,37"], ["Здание цеха", "199,50", "518,70"]]
    pages = _section_pages("5.2 Здание цеха", rows)
    index, pts = _ctx(pages)
    assert check_table_labels(pages, pts, index) == []


def test_blind_area_material_and_width_differ():
    pages = _pages(["5. Решения", "5.2 Здание цеха", "Отмостка - бетонная кл. В 7.5, шириной 1000 мм"],
                   ["7. Благоустройство", "Вокруг зданий выполняется асфальтобетонная отмостка шириной 1,5м."])
    index, pts = _ctx(pages)
    found = check_parameters(pts, index)
    assert [(f.field, f.object) for f in found] == [("blind_area", "all")]


def test_blind_area_width_after_class_abbreviation():
    pages = _pages(["5.2 Здание цеха", "Отмостка - бетонная кл. В 7.5, шириной 1000 мм. Кровля — плоская."],
                   ["7. Благоустройство", "Вокруг зданий выполняется бетонная отмостка шириной 1,0 м."])
    index, pts = _ctx(pages)
    assert check_parameters(pts, index) == []  # 1000 mm = 1,0 m


def test_roof_differs_in_kazakh():
    pages = _pages(["5.1 Қазандық ғимараты", "Шатыр — ПВХ-мембранадан жасалған жалпақ."],
                   ["7. Абаттандыру", "Ғимараттардың шатыры — профильденген табақтан жасалған еңісті."])
    index, pts = _ctx(pages)
    assert [(f.field, f.object) for f in check_parameters(pts, index)] == [("roof", "all")]


def test_failing_detector_becomes_warning(monkeypatch):
    pages = _pages(["5.1 Здание офиса", "Отмостка — бетонная шириной 1000 мм."])

    def boom(*_):
        raise RuntimeError("boom")

    monkeypatch.setattr(rules_v1, "DETECTORS", [("elevation", boom)] + rules_v1.DETECTORS[1:])
    findings, warnings = rules_v1.run_rules_v1(pages, run_rules(pages))
    assert len(warnings) == 1 and "elevation" in warnings[0]


def test_ids_continue_after_v0():
    pages = _pages(["Абсолютные отметки поверхности изменяются от 314,75 м до 315,04 м."],
                   ["5.1 Здание офиса", "Относительная отметка 0,000 соответствует абсолютной отметке 489,79 м."])
    v0 = run_rules(pages)
    findings, _ = rules_v1.run_rules_v1(pages, v0)
    assert [f.id for f in findings] == [f"P{len(v0.findings) + i}" for i in range(1, len(findings) + 1)]


def test_name_row_above_unlabelled_data_row():
    rows = [HEADER, ["Ед. изм", "м2", "м3"], ["Здание офиса", "", ""], ["", "199,50", "518,70"],
            ["ИТОГО", "199,50", "518,70"]]
    pages = _section_pages("5.2 Здание цеха", rows)
    index, pts = _ctx(pages)
    assert [f.field for f in check_table_labels(pages, pts, index)] == ["object_label"]


def test_relief_with_words_between_from_and_number():
    pages = _pages(["Высотные отметки разреза колеблются в пределах от высотных отметок 314,75 м до 315,04 м."],
                   ["5.1 Здание офиса",
                    "Условная отметка 0.000 соответствует абсолютной отметке - 489,79 по генплану."])
    index, pts = _ctx(pages)
    assert len(check_elevation(pts, index)) == 1


def test_unknown_name_flagged_only_where_repeated():
    office = PageTable([HEADER, ["Здание офиса", "312,91", "3116,37"]], (0, 40.0, 500, 80.0), HEADER)
    shop = PageTable([HEADER, ["Здание офиса", "199,50", "518,70"]], (0, 40.0, 500, 80.0), HEADER)
    pages = [_page(1, ["5.1 Административно-бытовой корпус", "Показатели", "Здание офиса 312,91 3116,37"],
                   [office]),
             _page(2, ["5.2 Здание цеха", "Показатели", "Здание офиса 199,50 518,70"], [shop])]
    index, pts = _ctx(pages)
    found = check_table_labels(pages, pts, index)
    assert [index.by_id()[f.object].name for f in found] == ["Здание цеха"]
