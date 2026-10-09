"""Held-out TEP wordings (generator profile v3) must stay out of the extractor."""

from __future__ import annotations

import json
import string
from pathlib import Path

from src.ner.common.tep_baseline import squash
from src.synthesis.data.heldout import HELDOUT

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDERS = {
    "eng_construction_volume_m3": {"v"},
    "eng_total_area_m2": {"v"},
    "object_axes": {"name", "floors", "a", "b"},
}


def _strings(x) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [s for v in x.values() for s in _strings(v)]
    return [s for v in x for s in _strings(v)]


def _lexicon_labels() -> set[str]:
    data = json.loads((ROOT / "src/ner/data/tep_lexicon.json").read_text(encoding="utf-8"))
    labels = [s for spec in data["fields"].values() for key in ("table", "text", "text_number_first")
              for s in _strings(spec.get(key, {}))]
    labels += _strings(data.get("negatives", {}))
    return {squash(x) for x in labels}


def test_halves_have_same_keys_and_do_not_overlap():
    for lang in ("ru", "kz"):
        dev, test = HELDOUT[lang]["dev"], HELDOUT[lang]["test"]
        assert dev.keys() == test.keys() == {"labels", "units", "templates"}
        for kind in dev:
            assert dev[kind].keys() == test[kind].keys(), (lang, kind)
        overlap = {squash(x) for x in _strings(dev["labels"])} & {squash(x) for x in _strings(test["labels"])}
        assert not overlap, overlap


def test_heldout_labels_are_not_in_lexicon():
    lexicon = _lexicon_labels()
    for lang, halves in HELDOUT.items():
        for half, kinds in halves.items():
            leaked = [x for x in _strings(kinds["labels"]) if squash(x) in lexicon]
            assert not leaked, (lang, half, leaked)


def test_templates_keep_placeholders():
    for lang, halves in HELDOUT.items():
        for kinds in halves.values():
            for name, variants in kinds["templates"].items():
                for t in variants:
                    names = {f for _, f, _, _ in string.Formatter().parse(t) if f}
                    assert PLACEHOLDERS[name] <= names, (lang, name, t)
                    assert names <= PLACEHOLDERS[name] | {"gen", "gen_cap"}, (lang, name, t)


def test_extractor_does_not_import_heldout():
    paths = [*(ROOT / "src/ner").rglob("*.py"), *(ROOT / "src/crossvalidation").rglob("*.py"),
             ROOT / "src/pipeline.py", *(ROOT / "api").rglob("*.py")]
    offenders = [str(p) for p in paths if "heldout" in p.read_text(encoding="utf-8")]
    assert not offenders, offenders
