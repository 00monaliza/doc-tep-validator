from __future__ import annotations

from src.crossvalidation.objects import page_texts
from src.crossvalidation.rules import Mention
from src.crossvalidation.rules_v1 import check_elevation, check_table_labels, check_volume_method
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
