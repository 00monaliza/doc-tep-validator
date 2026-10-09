"""Where checks live: a local folder (default) or Supabase (table `checks` + private bucket `checks`).

Supabase is used when SUPABASE_URL and SUPABASE_SECRET_KEY are set — this is how the Vercel
deployment runs, since a function's filesystem does not outlive the request. The leading
underscore keeps Vercel from turning this file into a function of its own.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi.responses import FileResponse, RedirectResponse, Response


class LocalStore:
    def __init__(self, root: Path):
        self.root = root

    def _dir(self, check_id: str) -> Path:
        return self.root / check_id

    def create(self, check_id: str, source: str, status: str = "pending", owner: str | None = None) -> None:
        (self._dir(check_id) / "files").mkdir(parents=True)
        (self._dir(check_id) / "meta.json").write_text(json.dumps({"source": source, "owner": owner}), encoding="utf-8")
        self._status(check_id, status)

    def transition(self, check_id: str, old: str, new: str) -> bool:
        """old -> new; False if the check was not in `old` (one process: no race to guard against)."""
        if (self.get(check_id) or {}).get("status") != old:
            return False
        self._status(check_id, new)
        return True

    def start(self, check_id: str) -> bool:
        return self.transition(check_id, "uploaded", "pending")

    def upload_targets(self, check_id: str, names: list[str]) -> dict[str, str]:
        """Where the browser PUTs each file: the local upload endpoint, guarded by a per-check token."""
        token = secrets.token_urlsafe(24)
        (self._dir(check_id) / "upload.json").write_text(json.dumps({"token": token, "names": names}), encoding="utf-8")
        return {n: f"/api/checks/{check_id}/upload/{quote(n)}?token={token}" for n in names}

    def accept_upload(self, check_id: str, name: str, token: str, data: bytes) -> bool:
        path = self._dir(check_id) / "upload.json"
        if not path.is_file():
            return False
        expected = json.loads(path.read_text(encoding="utf-8"))
        if not secrets.compare_digest(token, expected["token"]) or name not in expected["names"]:
            return False
        (self._dir(check_id) / "files" / name).write_bytes(data)
        return True

    def set_files(self, check_id: str, names: list[str]) -> None:
        pass  # the folder itself is the list

    def names(self, check_id: str) -> list[str]:
        path = self._dir(check_id) / "upload.json"
        if path.is_file():  # what the browser was told to upload
            return json.loads(path.read_text(encoding="utf-8"))["names"]
        return sorted(p.name for p in (self._dir(check_id) / "files").iterdir())

    def sections(self, check_id: str) -> dict[str, dict]:
        path = self._dir(check_id) / "sections.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def set_sections(self, check_id: str, sections: dict[str, dict]) -> None:
        (self._dir(check_id) / "sections.json").write_text(json.dumps(sections, ensure_ascii=False), encoding="utf-8")

    def _status(self, check_id: str, status: str, **extra) -> None:
        (self._dir(check_id) / "status.json").write_text(
            json.dumps({"status": status} | extra, ensure_ascii=False), encoding="utf-8")

    def put_files(self, check_id: str, files: list[tuple[str, bytes]]) -> None:
        for name, data in files:
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
        status["age"] = time.time() - path.stat().st_mtime  # seconds since the status last changed
        meta = self._dir(check_id) / "meta.json"
        status["owner"] = json.loads(meta.read_text(encoding="utf-8"))["owner"] if meta.is_file() else None
        if status["status"] == "done":
            status["report"] = json.loads((self._dir(check_id) / "report.json").read_text(encoding="utf-8"))
        return status

    def file_response(self, check_id: str, name: str) -> Response | None:
        path = self._dir(check_id) / "files" / name
        return FileResponse(path) if path.is_file() else None

    def file_link(self, check_id: str, name: str) -> str | None:
        """A URL the browser can open without our auth header (local runs have no auth)."""
        if not (self._dir(check_id) / "files" / name).is_file():
            return None
        return f"/api/checks/{check_id}/files/{quote(name)}"

    def reviews(self, check_id: str) -> dict[int, dict]:
        path = self._dir(check_id) / "reviews.json"
        if not path.is_file():
            return {}
        return {int(k): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}

    def set_review(self, check_id: str, finding: int, verdict: str | None, comment: str) -> None:
        reviews = self.reviews(check_id)
        if verdict is None and not comment:  # an empty review is no review
            reviews.pop(finding, None)
        else:
            reviews[finding] = {"verdict": verdict, "comment": comment}
        (self._dir(check_id) / "reviews.json").write_text(json.dumps(reviews, ensure_ascii=False), encoding="utf-8")

    def cleanup(self, days: float) -> int:
        """Delete checks older than `days`; returns how many were removed."""
        if not self.root.is_dir():
            return 0
        cutoff, n = time.time() - days * 86400, 0
        for d in self.root.iterdir():
            status = d / "status.json"
            if d.is_dir() and status.is_file() and status.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
                n += 1
        return n


class SupabaseStore:
    BUCKET = "checks"

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.http = httpx.Client(timeout=60, headers={"apikey": key, "Authorization": f"Bearer {key}"})

    @classmethod
    def from_env(cls) -> SupabaseStore | None:
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SECRET_KEY")
        return _supabase(url, key) if url and key else None

    def _rows(self, method: str, query: str = "", table: str = "checks", **kw) -> httpx.Response:
        r = self.http.request(method, f"{self.url}/rest/v1/{table}{query}", **kw)
        r.raise_for_status()
        return r

    @staticmethod
    def _key(check_id: str, name: str) -> str:
        # Storage keys allow ASCII only, and documents are named in Russian or Kazakh: the object is
        # stored under a hash of its name, the name itself stays in checks.files
        return f"{check_id}/{hashlib.sha1(name.encode()).hexdigest()[:20]}{Path(name).suffix.lower()}"

    def _obj(self, check_id: str, name: str) -> str:
        return f"{self.url}/storage/v1/object/{self.BUCKET}/{self._key(check_id, name)}"

    def _set(self, check_id: str, **fields) -> None:
        if "status" in fields:
            fields["status_changed_at"] = datetime.now(UTC).isoformat()
        self._rows("PATCH", f"?id=eq.{check_id}", json=fields)

    def create(self, check_id: str, source: str, status: str = "pending", owner: str | None = None) -> None:
        self._rows("POST", json={"id": check_id, "status": status, "source": source, "owner": owner})

    def transition(self, check_id: str, old: str, new: str) -> bool:
        """old -> new in one conditional update, so two requests cannot both make the step."""
        rows = self._rows("PATCH", f"?id=eq.{check_id}&status=eq.{old}", headers={"Prefer": "return=representation"},
                          json={"status": new, "status_changed_at": datetime.now(UTC).isoformat()}).json()
        return bool(rows)

    def start(self, check_id: str) -> bool:
        return self.transition(check_id, "uploaded", "pending")

    def upload_targets(self, check_id: str, names: list[str]) -> dict[str, str]:
        """Signed upload URLs (2 h): the browser sends files straight to Storage, past the 4.5 MB
        request limit of a Vercel function."""
        out = {}
        for n in names:
            r = self.http.post(f"{self.url}/storage/v1/object/upload/sign/{self.BUCKET}/{self._key(check_id, n)}",
                               headers={"x-upsert": "true"})
            r.raise_for_status()
            out[n] = f"{self.url}/storage/v1{r.json()['url']}"
        return out

    def accept_upload(self, check_id: str, name: str, token: str, data: bytes) -> bool:
        return False  # files go straight to Storage

    def set_files(self, check_id: str, names: list[str]) -> None:
        self._set(check_id, files=names)

    def sections(self, check_id: str) -> dict[str, dict]:
        rows = self._rows("GET", f"?id=eq.{check_id}&select=sections").json()
        return rows[0]["sections"] if rows else {}

    def set_sections(self, check_id: str, sections: dict[str, dict]) -> None:
        self._set(check_id, sections=sections)

    def put_files(self, check_id: str, files: list[tuple[str, bytes]]) -> None:
        names: list[str] = []
        try:
            for name, data in files:
                ctype = "application/pdf" if name.lower().endswith(".pdf") else "application/octet-stream"
                self.http.post(self._obj(check_id, name), content=data,
                               headers={"Content-Type": ctype, "x-upsert": "true"}).raise_for_status()
                names.append(name)
        finally:  # written once, and also on failure, so remove() finds what did get uploaded
            self._set(check_id, files=list(dict.fromkeys(names)))

    def names(self, check_id: str) -> list[str]:
        rows = self._rows("GET", f"?id=eq.{check_id}&select=files").json()
        return rows[0]["files"] if rows else []

    def remove(self, check_id: str) -> None:
        prefixes = [self._key(check_id, n) for n in self.names(check_id)]
        if prefixes:
            self.http.request("DELETE", f"{self.url}/storage/v1/object/{self.BUCKET}", json={"prefixes": prefixes})
        self._rows("DELETE", f"?id=eq.{check_id}")

    @contextmanager
    def files(self, check_id: str) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as tmp:
            for name in self.names(check_id):
                r = self.http.get(self._obj(check_id, name).replace("/object/", "/object/authenticated/", 1))
                r.raise_for_status()
                (Path(tmp) / name).write_bytes(r.content)
            yield Path(tmp)

    def finish(self, check_id: str, status: str, error: str | None = None,
               report: dict | None = None, trace: str | None = None) -> None:
        self._set(check_id, status=status, error=error, report=report)

    def get(self, check_id: str) -> dict | None:
        rows = self._rows("GET", f"?id=eq.{check_id}&select=status,error,report,status_changed_at,owner").json()
        if not rows:
            return None
        row = rows[0]
        changed = datetime.fromisoformat(row["status_changed_at"])
        out = {"status": row["status"], "age": (datetime.now(UTC) - changed).total_seconds(), "owner": row["owner"]}
        if row["status"] == "error":
            out["error"] = row["error"]
        if row["status"] == "done":
            out["report"] = row["report"]
        return out

    def file_link(self, check_id: str, name: str) -> str | None:
        """A signed URL (10 min): the browser opens the PDF straight from Storage."""
        if name not in self.names(check_id):
            return None
        r = self.http.post(self._obj(check_id, name).replace("/object/", "/object/sign/", 1), json={"expiresIn": 600})
        r.raise_for_status()
        return f"{self.url}/storage/v1{r.json()['signedURL']}"

    def file_response(self, check_id: str, name: str) -> Response | None:
        link = self.file_link(check_id, name)
        return RedirectResponse(link) if link else None

    def reviews(self, check_id: str) -> dict[int, dict]:
        rows = self._rows("GET", f"?check_id=eq.{check_id}&select=finding,verdict,comment", table="reviews").json()
        return {r["finding"]: {"verdict": r["verdict"], "comment": r["comment"]} for r in rows}

    def set_review(self, check_id: str, finding: int, verdict: str | None, comment: str) -> None:
        where = f"?check_id=eq.{check_id}&finding=eq.{finding}"
        if verdict is None and not comment:  # an empty review is no review
            self._rows("DELETE", where, table="reviews")
            return
        self._rows("POST", "?on_conflict=check_id,finding", table="reviews",
                   headers={"Prefer": "resolution=merge-duplicates"},
                   json={"check_id": check_id, "finding": finding, "verdict": verdict, "comment": comment,
                         "updated_at": datetime.now(UTC).isoformat()})

    def cleanup(self, days: float) -> int:
        """Delete checks (rows, reviews by cascade, files) older than `days`; returns how many were removed."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        n = 0
        while True:  # in batches, so a long backlog does not outgrow one request
            rows = self._rows("GET", "?select=id", params={"created_at": f"lt.{cutoff}", "limit": "100"}).json()
            for row in rows:
                self.remove(row["id"])
            n += len(rows)
            if len(rows) < 100:
                return n


@cache
def _supabase(url: str, key: str) -> SupabaseStore:
    """One store, and so one HTTP connection pool, per process instead of one per request."""
    return SupabaseStore(url, key)
