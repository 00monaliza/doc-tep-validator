from __future__ import annotations

from src.crossvalidation.objects import page_texts
from src.crossvalidation.rules_v1 import check_elevation
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
