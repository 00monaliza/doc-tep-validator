from src.ner.common.label_match import LabelMatcher, Match
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
