"""Where checks live: a local folder (default) or Supabase (table `checks` + private bucket `checks`).

Supabase is used when SUPABASE_URL and SUPABASE_SECRET_KEY are set — this is how the Vercel
deployment runs, since a function's filesystem does not outlive the request. The leading
underscore keeps Vercel from turning this file into a function of its own.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi.responses import FileResponse, RedirectResponse, Response


class LocalStore:
    def __init__(self, root: Path):
        self.root = root

    def _dir(self, check_id: str) -> Path:
        return self.root / check_id

    def create(self, check_id: str, source: str) -> None:
        (self._dir(check_id) / "files").mkdir(parents=True)
        self._status(check_id, "pending")

    def _status(self, check_id: str, status: str, **extra) -> None:
        (self._dir(check_id) / "status.json").write_text(
            json.dumps({"status": status} | extra, ensure_ascii=False), encoding="utf-8")

    def put_file(self, check_id: str, name: str, data: bytes) -> None:
        (self._dir(check_id) / "files" / name).write_bytes(data)

    def remove(self, check_id: str) -> None:
        shutil.rmtree(self._dir(check_id), ignore_errors=True)

    @contextmanager
    def files(self, check_id: str) -> Iterator[Path]:
        yield self._dir(check_id) / "files"

    def finish(self, check_id: str, status: str, error: str | None = None,
               report: dict | None = None, trace: str | None = None) -> None:
        if report is not None:
            (self._dir(check_id) / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        extra = {"error": error, "trace": trace} if status == "error" else {}
        self._status(check_id, status, **extra)

    def get(self, check_id: str) -> dict | None:
        path = self._dir(check_id) / "status.json"
        if not path.is_file():
            return None
        status = json.loads(path.read_text(encoding="utf-8"))
        status.pop("trace", None)
        if status["status"] == "done":
            status["report"] = json.loads((self._dir(check_id) / "report.json").read_text(encoding="utf-8"))
        return status

    def file_response(self, check_id: str, name: str) -> Response | None:
        path = self._dir(check_id) / "files" / name
        return FileResponse(path) if path.is_file() else None


class SupabaseStore:
    BUCKET = "checks"

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.http = httpx.Client(timeout=60, headers={"apikey": key, "Authorization": f"Bearer {key}"})

    @classmethod
    def from_env(cls) -> SupabaseStore | None:
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SECRET_KEY")
        return cls(url, key) if url and key else None

    def _rows(self, method: str, query: str = "", **kw) -> httpx.Response:
        r = self.http.request(method, f"{self.url}/rest/v1/checks{query}", **kw)
        r.raise_for_status()
        return r

    def _obj(self, check_id: str, name: str) -> str:
        return f"{self.url}/storage/v1/object/{self.BUCKET}/{check_id}/{quote(name)}"

    def create(self, check_id: str, source: str) -> None:
        self._rows("POST", json={"id": check_id, "status": "pending", "source": source})

    def put_file(self, check_id: str, name: str, data: bytes) -> None:
        ctype = "application/pdf" if name.lower().endswith(".pdf") else "application/octet-stream"
        self.http.post(self._obj(check_id, name), content=data,
                       headers={"Content-Type": ctype, "x-upsert": "true"}).raise_for_status()
        self._rows("PATCH", f"?id=eq.{check_id}", json={"files": self._names(check_id) + [name]})

    def _names(self, check_id: str) -> list[str]:
        rows = self._rows("GET", f"?id=eq.{check_id}&select=files").json()
        return rows[0]["files"] if rows else []

    def remove(self, check_id: str) -> None:
        prefixes = [f"{check_id}/{n}" for n in self._names(check_id)]
        if prefixes:
            self.http.request("DELETE", f"{self.url}/storage/v1/object/{self.BUCKET}", json={"prefixes": prefixes})
        self._rows("DELETE", f"?id=eq.{check_id}")

    @contextmanager
    def files(self, check_id: str) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as tmp:
            for name in self._names(check_id):
                r = self.http.get(self._obj(check_id, name).replace("/object/", "/object/authenticated/", 1))
                r.raise_for_status()
                (Path(tmp) / name).write_bytes(r.content)
            yield Path(tmp)

    def finish(self, check_id: str, status: str, error: str | None = None,
               report: dict | None = None, trace: str | None = None) -> None:
        self._rows("PATCH", f"?id=eq.{check_id}", json={"status": status, "error": error, "report": report})

    def get(self, check_id: str) -> dict | None:
        rows = self._rows("GET", f"?id=eq.{check_id}&select=status,error,report").json()
        if not rows:
            return None
        row = rows[0]
        out = {"status": row["status"]}
        if row["status"] == "error":
            out["error"] = row["error"]
        if row["status"] == "done":
            out["report"] = row["report"]
        return out

    def file_response(self, check_id: str, name: str) -> Response | None:
        if name not in self._names(check_id):
            return None
        r = self.http.post(self._obj(check_id, name).replace("/object/", "/object/sign/", 1), json={"expiresIn": 600})
        r.raise_for_status()
        return RedirectResponse(f"{self.url}/storage/v1{r.json()['signedURL']}")
