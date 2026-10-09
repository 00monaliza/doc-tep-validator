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
from src.ner.common.taxonomy import SYNTHETIC_TYPES, SYNTHETIC_TYPES_V1, TOLERANCES, DiscrepancyType, Verdict
from src.synthesis.formatting import fmt_num, parse_num
from src.synthesis.generator import generate_set

KZ_SPECIAL = set("ӘәҒғҚқҢңӨөҰұҮүҺһІі")
SEEDS = [1, 2, 3, 4, 5, 6]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def body_text(path) -> str:
    """PDF text without the running header (first line) and sheet number (last line) of every page,
    so a paragraph broken across pages reads contiguously."""
    pages = pdf.extract_text(path).split("\f")
    return norm(" ".join(" ".join(p.split("\n")[1:-1]) for p in pages))


def load(set_dir):
    return json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sets(tmp_path_factory):
    out = tmp_path_factory.mktemp("synthetic")
    result = {}
    for lang in ("ru", "kz"):
        for seed in SEEDS:
            inject = set(SYNTHETIC_TYPES) if seed == 1 else (set() if seed == 2 else None)
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
        body = body_text(set_dir / doc["text_pdf"])
        docx_text = norm(docx_reader.extract_text(set_dir / doc["docx"]))
        for fld, entry in fields.items():
            if not entry["present"]:
                assert entry["anchors"] == []
                continue
            assert entry["anchors"], f"{section}.{fld} not anchored"
            for a in entry["anchors"]:
                assert norm(a["text"]) in pdf_text, f"{section}.{fld}: {a['text']!r} not in PDF"
                if "context" in a:  # paragraph anchors: context + value must be contiguous in the text layer
                    assert norm(a["context"] + a["text"]) in body, f"{section}.{fld}: context not found"
                assert norm(a["text"]) in docx_text, f"{section}.{fld}: {a['text']!r} not in DOCX"


@pytest.mark.parametrize("lang", ["ru", "kz"])
@pytest.mark.parametrize("seed", SEEDS)
def test_object_mentions_anchored_in_pz(sets, lang, seed):
    """Every v2 statement (object tables, summary, sentences) is findable in the ПЗ text layer."""
    set_dir = sets[(lang, seed)]
    gt = load(set_dir)
    doc = gt["documents"]["PZ"]
    pdf_text = norm(pdf.extract_text(set_dir / doc["text_pdf"]))
    docx_text = norm(docx_reader.extract_text(set_dir / doc["docx"]))
    refs = [r for rec in gt["discrepancies"] + gt["consistent_checks"] for r in rec["refs"] if "mention" in r]
    assert refs
    for r in refs:
        for a in r["anchors"]:
            assert norm(a["text"]) in pdf_text and norm(a["text"]) in docx_text, r["mention"]
            if "context" in a:
                assert norm(a["context"] + a["text"]) in body_text(set_dir / doc["text_pdf"]), r["mention"]
    assert set(gt["objects"]) >= {r["object"] for r in refs} - {"all", "site"}


def test_v2_keeps_primary_building_values(tmp_path):
    """v2 only adds to v1: the primary building's TEP of a seed are the same in both profiles."""
    v1 = load(generate_set("ru", 5, tmp_path / "v1", scans=False, profile="v1"))
    v2 = load(generate_set("ru", 5, tmp_path / "v2", scans=False, profile="v2"))
    values = lambda g: {s: {f: e["value"] for f, e in fs.items()} for s, fs in g["tep"].items()}  # noqa: E731
    assert values(v1) == values(v2)
    assert v1["profile"] == "v1" and list(v1["objects"]) == ["b1"]
    assert not any(d["type"] not in {t.value for t in SYNTHETIC_TYPES_V1} for d in v1["discrepancies"])


def test_borderline_cases_present(tmp_path):
    """Some injected mismatches lie within 1-3 tolerances; some matches differ only by rounding."""
    near, rounded = 0, 0
    for seed in range(40, 60):
        gt = load(generate_set("ru", seed, tmp_path, set(SYNTHETIC_TYPES), scans=False))
        for d in gt["discrepancies"]:
            if d["type"] in ("TEP_CROSS_SECTION_MISMATCH", "TABLE_TOTAL_MISMATCH"):
                a, b = (d["refs"][-1]["value"], sum(r["value"] for r in d["refs"][:-1])) \
                    if d["type"] == "TABLE_TOTAL_MISMATCH" else (d["refs"][1]["value"], d["refs"][0]["value"])
                t = d["tolerance"]
                near += abs(a - b) <= 3 * max(t["abs"], t["rel"] * max(abs(a), abs(b))) + 1e-9
        rounded += sum(c["type"] == "TEP_CROSS_SECTION_MISMATCH" and c["refs"][0]["value"] != c["refs"][1]["value"]
                       for c in gt["consistent_checks"])
    assert near >= 3 and rounded >= 3


@pytest.mark.parametrize("lang", ["ru", "kz"])
def test_all_four_discrepancy_types_with_valid_refs(sets, lang):
    set_dir = sets[(lang, 1)]
    gt = load(set_dir)
    assert {d["type"] for d in gt["discrepancies"]} == {t.value for t in SYNTHETIC_TYPES}
    v1_types = {t.value for t in SYNTHETIC_TYPES_V1}
    for d in gt["discrepancies"]:
        refs = d["refs"]
        assert d["object"] and all(r["object"] for r in refs) and d["level"]
        if d["type"] not in v1_types:  # v2: refs point at ПЗ mentions, not the tep map
            assert all(r["mention"] and r["anchors"] for r in refs)
            if d["type"] == DiscrepancyType.PARAMETER_CONTRADICTION:
                assert len({r["value"] for r in refs}) > 1
            else:
                assert d["expected_verdict"] == Verdict.MISMATCH
                assert d["delta_abs"] != 0
                tol = TOLERANCES[DiscrepancyType(d["type"])]
                if d["type"] == DiscrepancyType.TABLE_TOTAL_MISMATCH:
                    assert not tol.matches(refs[-1]["value"], sum(r["value"] for r in refs[:-1]))
                else:
                    assert not tol.matches(refs[0]["value"], refs[1]["value"])
            continue
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
        refs = c["refs"]
        if c["type"] == DiscrepancyType.TABLE_TOTAL_MISMATCH:
            assert refs[-1]["value"] == pytest.approx(sum(r["value"] for r in refs[:-1]), abs=0.005)
        elif c["type"] == DiscrepancyType.TEP_CROSS_SECTION_MISMATCH:  # may be rounded differently
            assert TOLERANCES[DiscrepancyType(c["type"])].matches(refs[0]["value"], refs[1]["value"])
        elif c["type"] == DiscrepancyType.PARAMETER_CONTRADICTION:
            assert len({r["value"] for r in refs}) == 1
        else:
            assert refs[0]["value"] == refs[1]["value"]


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


@pytest.mark.parametrize("lang", ["ru", "kz"])
def test_v3_changes_only_wording(tmp_path, lang):
    """Same seed in v2 and v3: same buildings, values and discrepancies; only TEP wording differs."""
    v2 = load(generate_set(lang, 11, tmp_path / "v2", scans=False, profile="v2"))
    v3 = load(generate_set(lang, 11, tmp_path / "v3", scans=False, profile="v3-dev"))
    assert v3["profile"] == "v3-dev"
    assert v3["objects"] == v2["objects"]
    assert v3["injected_types"] == v2["injected_types"]
    core = lambda recs: [(r["type"], r.get("object"), [(x.get("field"), x.get("value")) for x in r["refs"]])  # noqa: E731
                         for r in recs]
    assert core(v3["discrepancies"]) == core(v2["discrepancies"])
    values = lambda g: {f: e["value"] for f, e in g["tep"]["PZ"].items()}  # noqa: E731
    assert values(v3) == values(v2)


@pytest.mark.parametrize("lang", ["ru", "kz"])
def test_v3_uses_heldout_labels(tmp_path, lang):
    from src.ner.common.tep_baseline import squash
    from src.synthesis.data.heldout import HELDOUT

    v2 = squash(body_text(generate_set(lang, 11, tmp_path / "v2", scans=False, profile="v2") / "text" / "PZ.pdf"))
    v3 = squash(body_text(generate_set(lang, 11, tmp_path / "v3", scans=False, profile="v3-dev") / "text" / "PZ.pdf"))
    labels = {squash(x) for v in HELDOUT[lang]["dev"]["labels"].values() for x in v}
    assert sum(lab in v3 for lab in labels) >= 3
    assert sum(lab in v2 for lab in labels) <= 1  # a held-out label may contain a v2 one, not the reverse


def test_ocr_noise_changes_one_spot():
    import random

    from src.synthesis.context import ocr_noise

    rng = random.Random(0)
    out = {ocr_noise("Площадь застройки здания", rng) for _ in range(50)}
    assert "Площадь застройки здания" not in out or len(out) > 1
    assert all(abs(len(x) - len("Площадь застройки здания")) <= 1 for x in out)
