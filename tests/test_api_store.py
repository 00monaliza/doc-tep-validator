import os
import time

import pytest
from fastapi.testclient import TestClient

import api.main
from api._store import LocalStore, SupabaseStore
from api.main import app


def _check(store: LocalStore, check_id: str, age_days: float) -> None:
    store.create(check_id, "upload")
    store.put_files(check_id, [("PZ.pdf", b"%PDF-1.4")])
    t = time.time() - age_days * 86400
    os.utime(store.root / check_id / "status.json", (t, t))


def test_local_cleanup_removes_only_old_checks(tmp_path):
    store = LocalStore(tmp_path)
    _check(store, "a" * 32, 10)
    _check(store, "b" * 32, 8)
    _check(store, "c" * 32, 1)
    assert store.cleanup(7) == 2
    assert [p.name for p in tmp_path.iterdir()] == ["c" * 32]


def test_local_cleanup_without_folder(tmp_path):
    assert LocalStore(tmp_path / "missing").cleanup(7) == 0


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api.main, "UPLOADS", tmp_path)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    return TestClient(app)


def test_cleanup_endpoint_needs_cron_secret(client, monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    assert client.get("/api/cron/cleanup", headers={"Authorization": "Bearer x"}).status_code == 401
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    assert client.get("/api/cron/cleanup").status_code == 401
    assert client.get("/api/cron/cleanup", headers={"Authorization": "Bearer wrong"}).status_code == 401
    r = client.get("/api/cron/cleanup", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200 and r.json()["deleted"] == 0


def test_vercel_without_storage_is_a_clear_error(client, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    r = client.post("/api/demo/ru")
    assert r.status_code == 503 and "SUPABASE" in r.json()["detail"]


def test_index_serves_the_interface(client):
    r = client.get("/")
    assert r.status_code == 200 and ("<div id=\"root\">" in r.text or "frontend" in r.text)


def test_capabilities_reports_ocr(client, monkeypatch):
    monkeypatch.setattr(api.main.shutil, "which", lambda _: None)
    assert client.get("/api/capabilities").json() == {"ocr": False}


def _done_check(client) -> str:
    check_id = client.post("/api/demo/ru").json()["id"]
    for _ in range(200):
        if client.get(f"/api/checks/{check_id}").json()["status"] != "pending":
            break
        time.sleep(0.05)
    return check_id


def test_reviews_roundtrip(client):
    check_id = _done_check(client)
    url = f"/api/checks/{check_id}/reviews"
    assert client.get(f"/api/checks/{check_id}").json()["reviews"] == {}
    assert client.put(f"{url}/0", json={"verdict": "confirmed"}).status_code == 200
    assert client.put(f"{url}/1", json={"verdict": "false_positive", "comment": " не то здание "}).status_code == 200
    assert client.get(f"/api/checks/{check_id}").json()["reviews"] == {
        "0": {"verdict": "confirmed", "comment": ""},
        "1": {"verdict": "false_positive", "comment": "не то здание"},
    }
    client.put(f"{url}/0", json={"verdict": None, "comment": ""})  # cleared
    assert set(client.get(f"/api/checks/{check_id}").json()["reviews"]) == {"1"}


def test_reviews_reject_bad_input(client):
    check_id = _done_check(client)
    url = f"/api/checks/{check_id}/reviews"
    assert client.put(f"{url}/0", json={"verdict": "maybe"}).status_code == 422
    assert client.put(f"{url}/999", json={"verdict": "confirmed"}).status_code == 404
    assert client.put(f"/api/checks/{'0' * 32}/reviews/0", json={"verdict": "confirmed"}).status_code == 404


SAMPLE = api.main.SAMPLES / "ru" / "ru_00001" / "text"


def _upload(client, names, review=True):
    files = [("files", (n, (SAMPLE / n).read_bytes())) for n in names]
    return client.post(f"/api/checks{'?review=1' if review else ''}", files=files)


def _wait(client, check_id):
    for _ in range(200):
        body = client.get(f"/api/checks/{check_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.05)
    raise AssertionError("check did not finish")


def test_review_upload_shows_detected_sections(client):
    r = _upload(client, ["PZ.pdf", "AR.docx", "KR.pdf", "SMETA.pdf"]).json()
    assert r["status"] == "uploaded"
    assert {n: f["section"] for n, f in r["files"].items()} == {
        "PZ.pdf": "PZ", "AR.docx": "AR", "KR.pdf": "KR", "SMETA.pdf": "SMETA"}
    body = client.get(f"/api/checks/{r['id']}").json()  # a reopened link resumes the review
    assert body["status"] == "uploaded" and set(body["files"]) == set(r["files"])


def test_start_with_choices(client):
    r = _upload(client, ["PZ.pdf", "AR.pdf", "KR.pdf", "SMETA.pdf"]).json()
    start = client.post(f"/api/checks/{r['id']}/start", json={"files": {"SMETA.pdf": "skip", "KR.pdf": "auto"}})
    assert start.status_code == 200
    report = _wait(client, r["id"])["report"]
    assert sorted(d["file"] for d in report["documents"]) == ["AR.pdf", "KR.pdf", "PZ.pdf"]
    assert report["completeness"]["missing"] == ["SMETA"]
    assert client.post(f"/api/checks/{r['id']}/start", json={}).status_code == 409  # only once


def test_start_section_override(client):
    r = _upload(client, ["PZ.pdf", "AR.pdf"]).json()
    client.post(f"/api/checks/{r['id']}/start", json={"files": {"AR.pdf": "KR"}})
    docs = {d["file"]: d for d in _wait(client, r["id"])["report"]["documents"]}
    assert docs["AR.pdf"]["section"] == "KR" and docs["AR.pdf"]["section_detected_by"] == "user"


def test_start_rejects_bad_choices(client):
    r = _upload(client, ["PZ.pdf"]).json()
    url = f"/api/checks/{r['id']}/start"
    assert client.post(url, json={"files": {"other.pdf": "PZ"}}).status_code == 400
    assert client.post(url, json={"files": {"PZ.pdf": "XX"}}).status_code == 422
    assert client.post(url, json={"files": {"PZ.pdf": "skip"}}).status_code == 400


def test_upload_without_review_runs_at_once(client):
    r = _upload(client, ["PZ.pdf", "AR.pdf"], review=False).json()
    assert r["status"] == "pending" and _wait(client, r["id"])["status"] == "done"


def test_storage_keys_are_ascii_for_cyrillic_names():
    a = SupabaseStore._key("f" * 32, "ПЗ Жилой дом.PDF")
    b = SupabaseStore._key("f" * 32, "ПЗ Жилой дом №2.pdf")
    assert a.isascii() and a.startswith("f" * 32 + "/") and a.endswith(".pdf")
    assert a != b and a == SupabaseStore._key("f" * 32, "ПЗ Жилой дом.PDF")


def test_cyrillic_file_names_roundtrip(client):
    files = [("files", ("ПЗ Жилой дом.pdf", (SAMPLE / "PZ.pdf").read_bytes()))]
    r = client.post("/api/checks?review=1", files=files).json()
    assert r["files"]["ПЗ Жилой дом.pdf"]["section"] == "PZ"
    assert client.get(f"/api/checks/{r['id']}/files/ПЗ Жилой дом.pdf").status_code == 200


def test_failed_upload_leaves_nothing(client, tmp_path, monkeypatch):
    def broken(self, check_id, files):
        raise OSError("disk full")
    monkeypatch.setattr(LocalStore, "put_files", broken)
    r = _upload(client, ["PZ.pdf"])
    assert r.status_code == 502
    assert list(tmp_path.iterdir()) == []


def test_bad_file_is_rejected_before_anything_is_stored(client, tmp_path):
    files = [("files", ("PZ.pdf", (SAMPLE / "PZ.pdf").read_bytes())), ("files", ("x.exe", b"MZ"))]
    assert client.post("/api/checks?review=1", files=files).status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_check_can_start_only_once(tmp_path):
    store = LocalStore(tmp_path)
    store.create("a" * 32, "upload", status="uploaded")
    assert store.start("a" * 32) is True
    assert store.start("a" * 32) is False


def test_stale_pending_check_is_reported_as_error(client, tmp_path):
    store = LocalStore(tmp_path)
    store.create("d" * 32, "upload")  # pending, but nobody is running it
    old = time.time() - 2 * 3600
    os.utime(tmp_path / ("d" * 32) / "status.json", (old, old))
    body = client.get(f"/api/checks/{'d' * 32}").json()
    assert body["status"] == "error" and "прервана" in body["error"]
