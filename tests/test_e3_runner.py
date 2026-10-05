import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exp_e3", ROOT / "scripts" / "exp_e3_compare.py")
exp_e3 = importlib.util.module_from_spec(spec)
sys.modules["exp_e3"] = exp_e3
spec.loader.exec_module(exp_e3)


class PerfectSystem:
    """Returns exactly the ground-truth slots of the set it is asked about (looked up from the directory)."""

    name = "perfect"

    def detect(self, paths, lang):
        import json

        from src.evaluation.bench import gt_slots

        gt = json.loads((paths[0].parent.parent / "ground_truth.json").read_text(encoding="utf-8"))
        return gt_slots(gt)


def test_run_synthetic_scores_every_set_with_perfect_system(tmp_path):
    board = exp_e3.run_synthetic(PerfectSystem(), "ru", [31, 32], "v1", tmp_path, "slot")
    assert len(board.records) == 2
    p, r, f1 = board.prf()
    assert r in (1.0, None) and p in (1.0, None)


def test_mean_sd_of_runs():
    import pytest

    mean, sd = exp_e3.mean_sd([0.5, 0.7, 0.6])
    assert mean == pytest.approx(0.6) and sd == pytest.approx(0.0816497, abs=1e-6)  # population sd
    assert exp_e3.mean_sd([0.5]) == (0.5, 0.0)
    assert exp_e3.mean_sd([]) == (None, None)


def test_llm_credentials_check_reads_env():
    assert exp_e3.has_llm_credentials({"ANTHROPIC_API_KEY": "k"})
    assert exp_e3.has_llm_credentials({"ANTHROPIC_AUTH_TOKEN": "t"})
    assert not exp_e3.has_llm_credentials({})
    assert not exp_e3.has_llm_credentials({"ANTHROPIC_API_KEY": ""})
