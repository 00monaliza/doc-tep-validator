"""End-to-end tests: synthetic package -> report, and the web API."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.main
from api.main import app
from src.ingestion.common.classify import detect_language
from src.pipeline import analyze_package
from src.synthesis.generator import generate_set

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "samples"


def key(dtype: str, field: str) -> tuple[str, str]:
    if dtype in ("COST_OBJECT_ESTIMATE_VS_SUMMARY", "AREA_PZ_VS_AR_EXPLICATION"):
        return dtype, ""
    return dtype, field.removeprefix("local_qty.")


def flagged(report: dict) -> set[tuple[str, str]]:
    return {key(f["type"], f["field"]) for f in report["findings"] if f["verdict"] != "MATCH"}


@pytest.fixture(scope="module")
def packages(tmp_path_factory):
    out = tmp_path_factory.mktemp("pkg")
    return {(lang, seed): generate_set(lang, seed, out, scans=False) for lang in ("ru", "kz") for seed in (31, 32, 33)}


@pytest.mark.parametrize("lang", ["ru", "kz"])
@pytest.mark.parametrize("seed", [31, 32, 33])
@pytest.mark.parametrize("kind", ["text/*.pdf", "text/*.docx"])
def test_report_matches_ground_truth(packages, lang, seed, kind):
    set_dir = packages[(lang, seed)]
    gt = json.loads((set_dir / "ground_truth.json").read_text(encoding="utf-8"))
    report = analyze_package(sorted(set_dir.glob(kind)))
    assert report["lang"] == lang
    assert report["completeness"]["missing"] == []
    assert flagged(report) == {key(d["type"], d["field"]) for d in gt["discrepancies"]}


def test_missing_section_reported(packages):
    set_dir = packages[("kz", 31)]
    report = analyze_package([p for p in sorted(set_dir.glob("text/*.pdf")) if p.stem != "KR"])
    assert report["completeness"]["missing"] == ["KR"]
    assert not any(f["type"] == "MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE" for f in report["findings"])


def test_highlight_coordinates_point_at_value(packages):
    """bbox of a table extraction must enclose the value text on its page."""
    import pdfplumber

    set_dir = packages[("ru", 31)]
    report = analyze_package(sorted(set_dir.glob("text/*.pdf")))
    e = report["tep"]["PZ"]["total_area_m2"]
    with pdfplumber.open(set_dir / "text" / "PZ.pdf") as pdf:
        text = pdf.pages[e["page"] - 1].within_bbox(e["bbox"]).extract_text()
    assert e["raw"] in text


@pytest.mark.parametrize(("text", "lang"), [
    ("Общая площадь здания составляет 1 247,79 м², строительный объём и высота по проекту", "ru"),
    ("Ғимараттың жалпы ауданы 2 118,34 м² құрайды және сәйкес бойынша үшін", "kz"),
    # Tesseract 'kaz' on Russian text: stray Kazakh letters must not flip the vote
    ("Здание 3-этажное, с подвалом и в осях по проекту на участке для ұ объекта", "ru"),
])
def test_detect_language(text, lang):
    assert detect_language(text) == lang


@pytest.fixture(autouse=False)
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(api.main, "UPLOADS", tmp_path)


def test_api_demo_roundtrip(uploads):
    client = TestClient(app)
    r = client.post("/api/demo/kz")
    assert r.status_code == 200
    check_id = r.json()["id"]
    for _ in range(50):
        body = client.get(f"/api/checks/{check_id}").json()
        if body["status"] != "pending":
            break
        time.sleep(0.1)
    assert body["status"] == "done"
    assert body["report"]["summary"]["MISMATCH"] == 3
    assert all("path" not in d for d in body["report"]["documents"])
    assert client.get(f"/api/checks/{check_id}/files/PZ.pdf").status_code == 200


def test_api_rejects_bad_input(uploads):
    client = TestClient(app)
    exe = ("files", ("x.exe", b"MZ", "application/octet-stream"))
    assert client.post("/api/checks", files=[exe]).status_code == 400
    assert client.get("/api/checks/..%2F..%2Fetc").status_code == 404
    assert client.get("/api/checks/" + "0" * 32).status_code == 404
