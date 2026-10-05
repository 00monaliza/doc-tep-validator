import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exp_e4", ROOT / "scripts" / "exp_e4_prepare.py")
exp_e4 = importlib.util.module_from_spec(spec)
sys.modules["exp_e4"] = exp_e4
spec.loader.exec_module(exp_e4)


def test_prepare_writes_pdfs_expected_and_observation_template(tmp_path, monkeypatch):
    monkeypatch.setattr(exp_e4, "SEEDS", [9000, 9001])
    dirs = exp_e4.prepare(tmp_path, langs=("ru",))
    assert [d.name for d in dirs] == ["ru_9000", "ru_9001"]
    assert sorted(p.stem for p in (dirs[0] / "text").glob("*.pdf")) == ["AR", "KR", "PZ", "SMETA"]
    expected = json.loads((dirs[0] / "expected.json").read_text(encoding="utf-8"))
    assert all({"id", "type", "field", "object"} <= set(e) for e in expected)
    rows = list(csv.DictReader((tmp_path / "observations.csv").open(encoding="utf-8")))
    assert {r["set"] for r in rows} == {"ru_9000", "ru_9001"}
    assert set(rows[0]) == {"set", "tool", "found_types", "false_alarms", "evidence_given", "language_ok", "notes"}


def test_prepare_does_not_ship_ground_truth_to_tool_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(exp_e4, "SEEDS", [9000])
    (d,) = exp_e4.prepare(tmp_path, langs=("kz",))
    assert not (d / "text" / "ground_truth.json").exists()
    assert not list(d.glob("**/ground_truth.json"))


def test_prepare_refuses_to_overwrite_hand_filled_observations(tmp_path, monkeypatch):
    monkeypatch.setattr(exp_e4, "SEEDS", [31])
    exp_e4.prepare(tmp_path, langs=("ru",))
    (tmp_path / "observations.csv").write_text("set,tool\nx,y\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        exp_e4.prepare(tmp_path, langs=("ru",))
    assert "x,y" in (tmp_path / "observations.csv").read_text(encoding="utf-8")
