import json

from src.evaluation.bench import gt_slots
from src.evaluation.systems import RulesSystem
from src.synthesis.generator import generate_set


def test_rules_system_matches_ground_truth_on_v1_set(tmp_path):
    set_dir = generate_set("ru", 31, tmp_path, scans=False, profile="v1")
    gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
    got = RulesSystem().detect(sorted(set_dir.glob("text/*.pdf")), "ru")
    assert got == gt_slots(gt)


def test_rules_system_returns_set_of_slots(tmp_path):
    set_dir = generate_set("kz", 32, tmp_path, scans=False, profile="v1")
    got = RulesSystem().detect(sorted(set_dir.glob("text/*.pdf")), "kz")
    assert isinstance(got, set) and all(isinstance(s, tuple) and len(s) == 2 for s in got)
    assert RulesSystem.name == "S1"
