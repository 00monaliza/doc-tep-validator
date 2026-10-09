"""MVP web service: upload a document package, get a TEP cross-check report.

Run:  uv run uvicorn api.main:app --reload     then open http://127.0.0.1:8000

POST /api/checks                    multipart `files` (PDF/DOCX) -> {id, status}
GET  /api/checks/{id}               status + report when done
GET  /api/checks/{id}/files/{name}  uploaded file (for the in-browser PDF viewer)
POST /api/demo/{lang}               run on the bundled synthetic sample (ru|kz)

Checks are kept in data/uploads/, or in Supabase when SUPABASE_URL and SUPABASE_SECRET_KEY are set
(see api/_store.py). On Vercel the analysis runs inside the POST request.
"""

from __future__ import annotations

import os
import re
import traceback
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response

from api._store import LocalStore, SupabaseStore
from src.ner.common.models import BACKBONES
from src.ner.common.taxonomy import DiscrepancyType
from src.pipeline import analyze_package

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "data" / "uploads"
STATIC = Path(__file__).parent / "static"
SAMPLES = ROOT / "data" / "synthetic" / "samples"
ALLOWED = {".pdf", ".docx"}
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_FILES = 20
ID_RE = re.compile(r"^[0-9a-f]{32}$")
SYNC_ANALYSIS = bool(os.environ.get("VERCEL") or os.environ.get("SYNC_ANALYSIS"))

app = FastAPI(title="ТЭП-валидатор", version="0.1.0")


def _store() -> LocalStore | SupabaseStore:
    store = SupabaseStore.from_env()
    if store:
        return store
    if os.environ.get("VERCEL"):  # the function's filesystem is read-only: checks have nowhere to live
        raise HTTPException(503, "Хранилище не настроено: задайте SUPABASE_URL и SUPABASE_SECRET_KEY")
    return LocalStore(UPLOADS)


def _valid_id(check_id: str) -> str:
    if not ID_RE.match(check_id):
        raise HTTPException(404, "check not found")
    return check_id


def _run(store: LocalStore | SupabaseStore, check_id: str) -> None:
    try:
        with store.files(check_id) as d:
            files = sorted(p for p in d.iterdir() if p.suffix.lower() in ALLOWED)
            report = analyze_package(files)
        for doc in report["documents"]:
            doc.pop("path", None)  # do not leak server paths
        store.finish(check_id, "done", report=report)
    except Exception as e:  # noqa: BLE001 — surface any analysis failure to the client
        store.finish(check_id, "error", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc(limit=3))


def _schedule(store: LocalStore | SupabaseStore, check_id: str, background: BackgroundTasks) -> None:
    # a serverless function may be frozen once it has answered, so there the check runs before the reply
    if SYNC_ANALYSIS:
        _run(store, check_id)
    else:
        background.add_task(_run, store, check_id)


@app.post("/api/checks")
async def create_check(files: list[UploadFile], background: BackgroundTasks) -> dict:
    if not files or len(files) > MAX_FILES:
        raise HTTPException(400, f"upload 1–{MAX_FILES} files")
    store, check_id = _store(), uuid.uuid4().hex
    store.create(check_id, "upload")
    for f in files:
        name = Path(f.filename or "").name
        if Path(name).suffix.lower() not in ALLOWED:
            store.remove(check_id)
            raise HTTPException(400, f"{name!r}: only PDF and DOCX are accepted")
        data = await f.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            store.remove(check_id)
            raise HTTPException(413, f"{name!r} is larger than {MAX_FILE_BYTES // 2**20} MB")
        store.put_file(check_id, name, data)
    _schedule(store, check_id, background)
    return {"id": check_id, "status": "pending"}


@app.post("/api/demo/{lang}")
def demo(lang: str, background: BackgroundTasks, kind: str = "text") -> dict:
    if lang not in ("ru", "kz") or kind not in ("text", "scan"):
        raise HTTPException(404, "unknown demo")
    store, check_id = _store(), uuid.uuid4().hex
    store.create(check_id, f"demo:{lang}:{kind}")
    for src in sorted((SAMPLES / lang / f"{lang}_00001" / kind).glob("*.pdf")):
        store.put_file(check_id, src.name, src.read_bytes())
    _schedule(store, check_id, background)
    return {"id": check_id, "status": "pending"}


@app.get("/api/checks/{check_id}")
def get_check(check_id: str) -> dict:
    status = _store().get(_valid_id(check_id))
    if status is None:
        raise HTTPException(404, "check not found")
    return {"id": check_id} | status


@app.get("/api/checks/{check_id}/files/{name}")
def get_file(check_id: str, name: str) -> Response:
    response = _store().file_response(_valid_id(check_id), Path(name).name)
    if response is None:
        raise HTTPException(404, "file not found")
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "discrepancy_types": [t.value for t in DiscrepancyType],
            "backbones": {lang: b.hub_id for lang, b in BACKBONES.items()}}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")
