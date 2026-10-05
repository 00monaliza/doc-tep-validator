from src.evaluation.ceiling import ceiling_table, classify_finding
from src.evaluation.schema import Finding, Ref
from src.ingestion.real import Page, PageTable


def page(number, text, rows=None, header=None):
    tables = [PageTable(rows=rows, bbox=(0, 0, 1, 1), header=header)] if rows else []
    return Page(number=number, text=text, lines=[], tables=tables)


def finding(level_type, refs, obj="b1", fld="total_area_m2"):
    return Finding(id="F1", level="numeric", type=level_type, field=fld, object=obj, refs=refs) \
        if level_type != "STATEMENT_CONTRADICTION" else \
        Finding(id="F1", level="logical", type=level_type, field=fld, object=obj, refs=refs)


def test_numeric_finding_with_value_in_header_matched_table_is_table_reachable():
    pages = [page(1, "Общая площадь 1247,79", rows=[["Показатель", "Значение"], ["x", "1247,79"]],
                  header=["Показатель", "Общая площадь"])]
    refs = [Ref(page=1, quote="1247,79", object="b1", value=1247.79)]
    # header regex for total_area_m2 must match "Общая площадь"
    assert classify_finding(finding("TEP_CROSS_SECTION_MISMATCH", refs), pages) == "table_reachable"


def test_value_only_in_text_is_text_reachable():
    pages = [page(1, "площадь здания составляет 1247,79 м2")]
    refs = [Ref(page=1, quote="1247,79", object="b1", value=1247.79)]
    assert classify_finding(finding("TEP_CROSS_SECTION_MISMATCH", refs), pages) == "text_reachable"


def test_logical_level_is_always_beyond_rules():
    pages = [page(1, "текст")]
    refs = [Ref(page=1, quote="текст", object="b1")]
    assert classify_finding(finding("STATEMENT_CONTRADICTION", refs), pages) == "beyond_rules"


def test_numeric_value_not_found_is_beyond_rules():
    pages = [page(1, "ничего похожего")]
    refs = [Ref(page=1, quote="ничего", object="b1", value=999.5)]
    assert classify_finding(finding("TEP_CROSS_SECTION_MISMATCH", refs), pages) == "beyond_rules"


def test_reference_without_numeric_value_is_beyond_rules():
    pages = [page(1, "текст")]
    refs = [Ref(page=1, quote="текст", object="b1")]
    assert classify_finding(finding("TEP_CROSS_SECTION_MISMATCH", refs), pages) == "beyond_rules"


def test_ceiling_table_counts_by_level_and_class():
    pages = [page(1, "1247,79 м2")]
    a = finding("TEP_CROSS_SECTION_MISMATCH", [Ref(page=1, quote="1247,79", object="b1", value=1247.79)])
    b = finding("STATEMENT_CONTRADICTION", [Ref(page=1, quote="1247,79", object="b1")])
    table = ceiling_table([(a, classify_finding(a, pages)), (b, classify_finding(b, pages))])
    assert table["numeric"]["text_reachable"] == 1 and table["logical"]["beyond_rules"] == 1
