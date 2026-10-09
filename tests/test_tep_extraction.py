"""Extractor regressions: profile v2 stays perfect, the real dev document does not get worse."""

from __future__ import annotations

import json

import pytest

from src.evaluation.annotations import ANNOTATIONS_DIR, load_annotation, source_path
from src.evaluation.extraction_eval import Scores, gold_slots, predicted_slots, real_verdicts
from src.ingestion.real import load_pages
from src.ner.common.tep_baseline import STAGES, extract
from src.synthesis.generator import generate_set

V2_SEEDS = [7000, 7001, 7002, 7003]


@pytest.fixture(scope="module")
def v2_sets(tmp_path_factory):
    out = tmp_path_factory.mktemp("v2")
    return [generate_set(lang, seed, out, scans=False, profile="v2") for lang in ("ru", "kz") for seed in V2_SEEDS]


@pytest.mark.parametrize("stages", [STAGES[:1], STAGES])
def test_v2_slots_are_perfect(v2_sets, stages):
    scores = Scores()
    for set_dir in v2_sets:
        gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
        gold = gold_slots(gt)
        pred, _ = predicted_slots(extract(load_pages(set_dir / "text" / "PZ.pdf"), stages=stages), gt, gold)
        scores.add(pred, gold)
    p, r, _, n = scores.prf()
    assert n > 0 and p == 1.0 and r == 1.0, (stages, scores.fp, scores.fn)


def test_real_dev_document_does_not_regress():
    paths = sorted(ANNOTATIONS_DIR.glob("*.json"))
    anns = [a for a in map(load_annotation, paths) if source_path(a).exists()]
    if not anns:
        pytest.skip("реального документа нет в рабочей копии (data/real в .gitignore)")
    for ann in anns:
        verdicts = [v for *_, v in real_verdicts(extract(load_pages(source_path(ann))), ann)]
        assert verdicts.count("ok") >= 8, verdicts
        assert not [v for v in verdicts if v.startswith("wrong")], verdicts
