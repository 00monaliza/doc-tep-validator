from src.ner.common.label_match import LabelMatcher, Match, tokens, word_matches
from src.ner.common.lexicon import load_lexicon


def matcher(**kw) -> LabelMatcher:
    return LabelMatcher(load_lexicon(), **kw)


def test_exact_is_the_old_field_of():
    m = matcher(methods=("exact",), unit_check=False)
    lex = load_lexicon()
    for text in ("Площадь застройки, м²", "Этажность", "Ғимараттың жалпы ауданы", "Строительный объем"):
        assert m.match(text).field == lex.field_of(text)
    assert m.match("Классная комната") is None
    assert m.match("1 247,79") is None


def test_unit_check_excludes_incompatible_fields():
    m = matcher(methods=("exact",))
    assert m.match("Площадь застройки", "m2") == Match("building_area_m2", 1.0, "exact")
    assert m.match("Площадь застройки", "m3") is None
    assert matcher(methods=("exact",), unit_check=False).match("Площадь застройки", "m3").field == "building_area_m2"


def test_text_labels_only_in_text():
    m = matcher(methods=("exact",))
    assert m.match("объём здания котельной равен", "m3", where="text").field == "construction_volume_m3"
    assert m.match("Объём", "m3") is None  # a bare 'объём' cell is not a TEP label in a table



FULL = ("exact", "fuzzy")


def test_tokens_mark_truncations_and_fix_lookalikes():
    assert tokens("Пл. застр.") == [("пл", True), ("застр", True)]
    assert tokens("кол-во") == [("кол", True)]
    assert tokens("Oбщая") == [("общая", False)]  # Latin O
    assert tokens("S общ.") == [("площадь", False), ("общ", True)]


def test_word_matching():
    assert word_matches("общей", False, "общая")
    assert word_matches("плошадь", False, "площадь")  # one OCR edit
    assert word_matches("пл", True, "площадь")
    assert not word_matches("стоимость", False, "строительный")
    assert not word_matches("пл", False, "площадь")  # without a dot it is not a truncation


def test_fuzzy_reads_unseen_wordings():
    m = matcher(methods=FULL)
    assert m.match("Пл. застр. корпуса", "m2").field == "building_area_m2"
    assert m.match("Oбщ. площадь корпуса", "m2").field == "total_area_m2"
    assert m.match("Кол-во этажей", None).field == "floors"
    assert m.match("Объём строительный здания", "m3").field == "construction_volume_m3"
    assert m.match("Пл. застр. корпуса", "m2").method == "fuzzy"


def test_fuzzy_abstains_on_non_tep():
    m = matcher(methods=FULL)
    assert m.match("Здание котельной") is None
    assert m.match("Площадь участка", "m2") is None
    assert m.match("Площадь", "m2") is None  # which area? ambiguous
