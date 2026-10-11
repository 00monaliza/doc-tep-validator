from src.ner.common.parameters import load_parameters, width_mm


def test_parameters_loaded():
    p = load_parameters()
    assert {"blind_area", "roof", "clear_height", "floor_height"} <= set(p)


def test_longest_material_wins():
    blind = load_parameters()["blind_area"]
    assert blind.material_in("асфальтобетонная отмостка шириной 1,5м") == "asphalt"
    assert blind.material_in("Отмостка - бетонная кл. В 7.5, шириной 1000 мм") == "concrete"
    assert blind.material_in("Отмостка шириной 1 м") is None


def test_width_in_mm():
    assert width_mm("Отмостка - бетонная кл. В 7.5, шириной 1000 мм") == 1000
    assert width_mm("асфальтобетонная отмостка шириной 1,5м") == 1500
    assert width_mm("Отмостка — бетон, ені 1,2 м.") == 1200
    assert width_mm("Отмостка бетонная.") is None


def test_mentions():
    p = load_parameters()
    assert p["blind_area"].mention_re.search("Отмостка — бетон")
    assert p["roof"].mention_re.search("Ғимараттардың шатыры — жалпақ")
    assert not p["roof"].mention_re.search("Отмостка — бетон")
