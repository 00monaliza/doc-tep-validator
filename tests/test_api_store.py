import os
import time

import pytest
from fastapi.testclient import TestClient

import api.main
from api._store import LocalStore
from api.main import app


def _check(store: LocalStore, check_id: str, age_days: float) -> None:
    store.create(check_id, "upload")
    store.put_file(check_id, "PZ.pdf", b"%PDF-1.4")
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
