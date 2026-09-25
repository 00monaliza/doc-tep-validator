"""Integrity tests for the bilingual synthetic generator.

The key property: ground truth must be *reachable* from the rendered documents —
every present TEP value is findable at its anchor in the PDF and DOCX text,
every deliberately missing TEP is absent, and injected discrepancies are exactly
the pairs that disagree beyond the taxonomy tolerances.
"""

from __future__ import annotations

import json
import re

import pytest

from src.ingestion.common import docx_reader, pdf
from src.ner.common.taxonomy import TOLERANCES, DiscrepancyType, Verdict
from src.synthesis.formatting import fmt_num, parse_num
from src.synthesis.generator import generate_set

KZ_SPECIAL = set("ӘәҒғҚқҢңӨөҰұҮүҺһІі")
SEEDS = [1, 2, 3, 4, 5, 6]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def load(set_dir):
    return json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sets(tmp_path_factory):
    out = tmp_path_factory.mktemp("synthetic")
    result = {}
    for lang in ("ru", "kz"):
        for seed in SEEDS:
            inject = set(DiscrepancyType) if seed == 1 else (set() if seed == 2 else None)
            result[(lang, seed)] = generate_set(lang, seed, out, inject, scans=seed == 1)
    return result


def test_number_format_roundtrip():
    assert fmt_num(1234567.891, 3) == "1 234 567,891"
    assert parse_num("1 234 567,891") == pytest.approx(1234567.891)
    assert parse_num("12 345,6") == pytest.approx(12345.6)


@pytest.mark.parametrize("lang", ["ru", "kz"])
@pytest.mark.parametrize("seed", SEEDS)
def test_anchors_present_in_pdf_and_docx(sets, lang, seed):
    set_dir = sets[(lang, seed)]
    gt = load(set_dir)
    for section, fields in gt["tep"].items():
        doc = gt["documents"][section]
        pdf_text = norm(pdf.extract_text(set_dir / doc["text_pdf"]))
        docx_text = norm(docx_reader.extract_text(set_dir / doc["docx"]))
        for fld, entry in fields.items():
            if not entry["present"]:
                assert entry["anchors"] == []
                continue
            assert entry["anchors"], f"{section}.{fld} not anchored"
            for a in entry["anchors"]:
                assert norm(a["text"]) in pdf_text, f"{section}.{fld}: {a['text']!r} not in PDF"
                assert norm(a["text"]) in docx_text, f"{section}.{fld}: {a['text']!r} not in DOCX"


@pytest.mark.parametrize("lang", ["ru", "kz"])
def test_all_four_discrepancy_types_with_valid_refs(sets, lang):
    set_dir = sets[(lang, 1)]
    gt = load(set_dir)
    assert {d["type"] for d in gt["discrepancies"]} == {t.value for t in DiscrepancyType}
    for d in gt["discrepancies"]:
        refs = d["refs"]
        for r in refs:  # tep_ref resolves to the same value stored in the tep map
            section, fld = r["tep_ref"].split(".", 1)
            assert gt["tep"][section][fld]["value"] == r["value"]
        if d["type"] == DiscrepancyType.MISSING_MANDATORY_TEP:
            missing, reference = refs
            assert d["expected_verdict"] == Verdict.MISSING
            assert missing["value"] is None and missing["anchors"] == []
            assert reference["value"] is not None and reference["anchors"]
            # the reference value must not leak into the section where it is missing
            text = norm(pdf.extract_text(set_dir / gt["documents"][missing["section"]]["text_pdf"]))
            assert reference["anchors"][0]["text"] not in text
        else:
            a, b = refs[0]["value"], refs[1]["value"]
            assert d["expected_verdict"] == Verdict.MISMATCH
            assert not TOLERANCES[DiscrepancyType(d["type"])].matches(a, b)


@pytest.mark.parametrize("lang", ["ru", "kz"])
def test_clean_set_has_no_discrepancies(sets, lang):
    gt = load(sets[(lang, 2)])
    assert gt["discrepancies"] == []
    for c in gt["consistent_checks"]:
        assert c["expected_verdict"] == Verdict.MATCH
        assert c["refs"][0]["value"] == c["refs"][1]["value"]


@pytest.mark.parametrize("lang", ["ru", "kz"])
@pytest.mark.parametrize("seed", SEEDS)
def test_sections_are_internally_consistent(sets, lang, seed):
    gt = load(sets[(lang, seed)])
    ar, sm = gt["tep"]["AR"], gt["tep"]["SMETA"]
    val = lambda sec, f: gt["tep"][sec][f]["value"]  # noqa: E731
    rooms = sum(r["area_m2"] for r in gt["ar_explication"])
    assert ar["explication_total_area_m2"]["value"] == pytest.approx(rooms, abs=0.01)
    os_rows = sum(v["value"] for k, v in sm.items() if k.startswith("os.ls_"))
    assert val("SMETA", "os.total_ktg") == pytest.approx(os_rows, abs=0.002)
    assert val("SMETA", "os.ls_02-01-01_ktg") == pytest.approx(val("SMETA", "local.total_tg") / 1000, abs=0.001)
    chapters = sum(v["value"] for k, v in sm.items() if re.match(r"ssr\.ch\d", k))
    assert val("SMETA", "ssr.subtotal_ktg") == pytest.approx(chapters, abs=0.002)
    if gt["tep"]["PZ"]["estimated_cost_ktg"]["present"]:
        assert val("PZ", "estimated_cost_ktg") == val("SMETA", "ssr.total_ktg")


@pytest.mark.parametrize("lang", ["ru", "kz"])
def test_scan_is_image_only(sets, lang):
    set_dir = sets[(lang, 1)]
    gt = load(set_dir)
    for doc in gt["documents"].values():
        scan = set_dir / doc["scan_pdf"]
        assert not pdf.has_text_layer(scan)
        assert len(pdf.rasterize(scan, dpi=30)) == len(pdf.rasterize(set_dir / doc["text_pdf"], dpi=30))
        assert len(doc["scan_pages"]) == len(doc["scan_params"])


def test_kazakh_letters_survive_in_text_layer(sets):
    set_dir = sets[("kz", 1)]
    gt = load(set_dir)
    # DOCX stores the source strings verbatim, so it is the reference for what was written.
    # (Capital Ң never starts a Kazakh word, so not all 18 letters occur naturally;
    # rendering of the full set is covered by scripts/check_env.py.)
    pdf_text = "".join(pdf.extract_text(set_dir / d["text_pdf"]) for d in gt["documents"].values())
    src_text = "".join(docx_reader.extract_text(set_dir / d["docx"]) for d in gt["documents"].values())
    assert set(pdf_text) & KZ_SPECIAL == set(src_text) & KZ_SPECIAL
    assert set("әғқңөұүһі") <= set(pdf_text)
    assert "?" not in pdf_text and "�" not in pdf_text


def test_parallel_sets_share_structure_not_content(sets):
    ru, kz = load(sets[("ru", 1)]), load(sets[("kz", 1)])
    strip = lambda g, s: {k for k in g["tep"][s] if not k.startswith("room.")}  # noqa: E731
    for section in ("PZ", "KR", "SMETA"):
        assert strip(ru, section) == strip(kz, section)
    assert [d["type"] for d in ru["discrepancies"]] == [d["type"] for d in kz["discrepancies"]]
    assert ru["tep"]["SMETA"]["ssr.total_ktg"]["value"] != kz["tep"]["SMETA"]["ssr.total_ktg"]["value"]


def test_deterministic(tmp_path):
    a = load(generate_set("kz", 7, tmp_path / "a", scans=False))
    b = load(generate_set("kz", 7, tmp_path / "b", scans=False))
    assert a["tep"] == b["tep"] and a["discrepancies"] == b["discrepancies"]
