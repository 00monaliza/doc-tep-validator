"""MVP web service: upload a document package, get a TEP cross-check report.

Run:  uv run uvicorn api.main:app --reload     then open http://127.0.0.1:8000

POST /api/checks                    multipart `files` (PDF/DOCX) -> {id, status}; with ?review=1 the check waits
                                    in status "uploaded" with each file's detected section, until /start
POST /api/checks/init               {files: [{name, size}]} -> {id, uploads: {name: url}}; the browser PUTs each
                                    file to its url (Supabase signed URL, or /upload locally), then calls
POST /api/checks/{id}/uploaded      -> status "uploaded" with each file's detected section
POST /api/checks/{id}/start         {files: {name: "PZ"|"AR"|"KR"|"SMETA"|"auto"|"skip"}} -> run the check
GET  /api/checks/{id}               status + report when done
GET  /api/checks/{id}/files/{name}  uploaded file (for the in-browser PDF viewer)
POST /api/demo/{lang}               run on the bundled synthetic sample (ru|kz)
PUT  /api/checks/{id}/reviews/{n}    expert verdict on finding n: {verdict: confirmed|false_positive|null, comment}
GET  /api/capabilities              what this server can do: {"ocr": bool} (no Tesseract on Vercel)
GET  /api/cron/cleanup              delete checks older than RETENTION_DAYS (Vercel Cron, CRON_SECRET)
GET  /                              the React interface from frontend/dist (npm --prefix frontend run build)

Checks are kept in data/uploads/, or in Supabase when SUPABASE_URL and SUPABASE_SECRET_KEY are set
(see api/_store.py). On Vercel the analysis runs inside the POST request.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import traceback
import uuid
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api._store import LocalStore, SupabaseStore
from src.ner.common.models import BACKBONES
from src.ner.common.taxonomy import DiscrepancyType, Section
from src.pipeline import analyze_package, classify_file

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "data" / "uploads"
FRONTEND = ROOT / "frontend" / "dist"
SAMPLES = ROOT / "data" / "synthetic" / "samples"
ALLOWED = {".pdf", ".docx"}
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_FILES = 20
ID_RE = re.compile(r"^[0-9a-f]{32}$")
RETENTION_DAYS = float(os.environ.get("RETENTION_DAYS", "7"))
SYNC_ANALYSIS = bool(os.environ.get("VERCEL") or os.environ.get("SYNC_ANALYSIS"))
# a check still "pending" after this long was cut off (function time limit, server restart)
STALE_AFTER_S = 330 if SYNC_ANALYSIS else 1800  # 300 s = maxDuration in vercel.json

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
        chosen = store.sections(check_id)  # the user's choice before the start, if any
        with store.files(check_id) as d:
            files = sorted(p for p in d.iterdir()
                           if p.suffix.lower() in ALLOWED and chosen.get(p.name, {}).get("use", True))
            overrides = {n: Section(c["section"]) for n, c in chosen.items() if c.get("user") and c.get("section")}
            report = analyze_package(files, overrides)
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


def _classify_path(path: Path) -> dict:
    try:
        section, how = classify_file(path)
    except Exception:  # noqa: BLE001 — an unreadable file is the user's to sort out before the start
        section, how = None, "unreadable"
    return {"section": section.value if section else None, "how": how, "use": True, "user": False}


def _classify(name: str, data: bytes) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        path.write_bytes(data)
        return _classify_path(path)


def _check_name(name: str) -> str:
    name = Path(name or "").name
    if Path(name).suffix.lower() not in ALLOWED:
        raise HTTPException(400, f"{name!r}: only PDF and DOCX are accepted")
    return name


class FileSpec(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    size: int = Field(ge=1)


class Init(BaseModel):
    files: list[FileSpec] = Field(min_length=1, max_length=MAX_FILES)


@app.post("/api/checks/init")
def init_check(body: Init) -> dict:
    names = [_check_name(f.name) for f in body.files]
    if len(set(names)) != len(names):
        raise HTTPException(400, "file names repeat")
    for f in body.files:
        if f.size > MAX_FILE_BYTES:
            raise HTTPException(413, f"{f.name!r} is larger than {MAX_FILE_BYTES // 2**20} MB")
    store, check_id = _store(), uuid.uuid4().hex
    store.create(check_id, "upload", status="receiving")
    try:
        store.set_files(check_id, names)
        uploads = store.upload_targets(check_id, names)
    except Exception as e:  # noqa: BLE001
        store.remove(check_id)
        raise HTTPException(502, f"Загрузка не подготовлена: {type(e).__name__}") from e
    return {"id": check_id, "uploads": uploads}


@app.put("/api/checks/{check_id}/upload/{name}")
async def upload_file(check_id: str, name: str, token: str, request: Request) -> dict:
    """The local stand-in for a Storage signed URL."""
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, f"{name!r} is larger than {MAX_FILE_BYTES // 2**20} MB")
    if not _store().accept_upload(_valid_id(check_id), Path(name).name, token, bytes(data)):
        raise HTTPException(403, "upload not allowed")
    return {"name": name, "size": len(data)}


@app.post("/api/checks/{check_id}/uploaded")
def uploaded(check_id: str) -> dict:
    store = _store()
    status = store.get(_valid_id(check_id))
    if status is None:
        raise HTTPException(404, "check not found")
    if status["status"] != "receiving":
        raise HTTPException(409, "files already received")
    try:
        with store.files(check_id) as d:
            present = {p.name: p for p in d.iterdir()}
            missing = [n for n in store.names(check_id) if n not in present]
            if missing:
                raise HTTPException(400, f"не загрузились: {', '.join(missing)}")
            sections = {n: _classify_path(p) for n, p in present.items()}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 — e.g. an object that never reached Storage
        raise HTTPException(400, f"не все файлы загрузились ({type(e).__name__})") from e
    store.set_sections(check_id, sections)
    if not store.transition(check_id, "receiving", "uploaded"):
        raise HTTPException(409, "files already received")
    return {"id": check_id, "status": "uploaded", "files": sections}


@app.post("/api/checks")
def create_check(files: list[UploadFile], background: BackgroundTasks, review: bool = False) -> dict:
    # a plain `def`: FastAPI runs it in a worker thread, so PDF parsing and storage calls do not block the loop
    if not files or len(files) > MAX_FILES:
        raise HTTPException(400, f"upload 1–{MAX_FILES} files")
    received: list[tuple[str, bytes]] = []
    for f in files:  # everything is checked before anything is stored
        name = Path(f.filename or "").name
        if Path(name).suffix.lower() not in ALLOWED:
            raise HTTPException(400, f"{name!r}: only PDF and DOCX are accepted")
        data = f.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, f"{name!r} is larger than {MAX_FILE_BYTES // 2**20} MB")
        received.append((name, data))
    store, check_id = _store(), uuid.uuid4().hex
    store.create(check_id, "upload", status="uploaded" if review else "pending")
    try:
        store.put_files(check_id, received)
        if review:
            sections = {name: _classify(name, data) for name, data in received}
            store.set_sections(check_id, sections)
    except Exception as e:  # noqa: BLE001 — leave no half-stored check behind
        store.remove(check_id)
        raise HTTPException(502, f"Файлы не сохранены: {type(e).__name__}") from e
    if review:
        return {"id": check_id, "status": "uploaded", "files": sections}
    _schedule(store, check_id, background)
    return {"id": check_id, "status": "pending"}


class Start(BaseModel):
    files: dict[str, Literal["PZ", "AR", "KR", "SMETA", "auto", "skip"]] = {}


@app.post("/api/checks/{check_id}/start")
def start_check(check_id: str, body: Start, background: BackgroundTasks) -> dict:
    store = _store()
    status = store.get(_valid_id(check_id))
    if status is None:
        raise HTTPException(404, "check not found")
    if status["status"] != "uploaded":
        raise HTTPException(409, "check already started")
    sections = store.sections(check_id)
    unknown = set(body.files) - set(sections)
    if unknown:
        raise HTTPException(400, f"unknown files: {sorted(unknown)}")
    for name, choice in body.files.items():
        c = sections[name]
        c["use"] = choice != "skip"
        if choice not in ("auto", "skip"):
            c["user"], c["section"] = True, choice
    if not any(c["use"] for c in sections.values()):
        raise HTTPException(400, "no files left to check")
    store.set_sections(check_id, sections)
    if not store.start(check_id):  # someone started it in the meantime
        raise HTTPException(409, "check already started")
    _schedule(store, check_id, background)
    return {"id": check_id, "status": "pending"}


@app.post("/api/demo/{lang}")
def demo(lang: str, background: BackgroundTasks, kind: str = "text") -> dict:
    if lang not in ("ru", "kz") or kind not in ("text", "scan"):
        raise HTTPException(404, "unknown demo")
    store, check_id = _store(), uuid.uuid4().hex
    store.create(check_id, f"demo:{lang}:{kind}")
    store.put_files(check_id, [(src.name, src.read_bytes())
                               for src in sorted((SAMPLES / lang / f"{lang}_00001" / kind).glob("*.pdf"))])
    _schedule(store, check_id, background)
    return {"id": check_id, "status": "pending"}


@app.get("/api/checks/{check_id}")
def get_check(check_id: str) -> dict:
    store = _store()
    status = store.get(_valid_id(check_id))
    if status is None:
        raise HTTPException(404, "check not found")
    if status.pop("age", 0) > STALE_AFTER_S and status["status"] == "pending":
        status = {"status": "error", "error": "проверка прервана: превышено время обработки, загрузите файлы заново"}
    if status["status"] == "done":
        status["reviews"] = {str(k): v for k, v in store.reviews(check_id).items()}
    if status["status"] == "uploaded":
        status["files"] = store.sections(check_id)
    return {"id": check_id} | status


class Review(BaseModel):
    verdict: Literal["confirmed", "false_positive"] | None = None
    comment: str = Field(default="", max_length=2000)


@app.put("/api/checks/{check_id}/reviews/{finding}")
def put_review(check_id: str, finding: int, review: Review) -> dict:
    store = _store()
    status = store.get(_valid_id(check_id))
    if status is None or status["status"] != "done":
        raise HTTPException(404, "check not found")
    if not 0 <= finding < len(status["report"]["findings"]):
        raise HTTPException(404, "finding not found")
    store.set_review(check_id, finding, review.verdict, review.comment.strip())
    return {"finding": finding, "verdict": review.verdict, "comment": review.comment.strip()}


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


@app.get("/api/capabilities")
def capabilities() -> dict:
    return {"ocr": shutil.which("tesseract") is not None}


@app.get("/api/cron/cleanup")
def cleanup(authorization: str | None = Header(default=None)) -> dict:
    # Vercel Cron sends "Bearer $CRON_SECRET"; without the secret configured the endpoint stays closed
    secret = os.environ.get("CRON_SECRET")
    if not secret or authorization != f"Bearer {secret}":
        raise HTTPException(401, "unauthorized")
    return {"deleted": _store().cleanup(RETENTION_DAYS), "retention_days": RETENTION_DAYS}


if (FRONTEND / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    page = FRONTEND / "index.html"
    if page.is_file():
        return page.read_text(encoding="utf-8")
    return ("<p>Интерфейс не собран: выполните <code>npm --prefix frontend ci</code> и "
            "<code>npm --prefix frontend run build</code> или запустите <code>npm --prefix frontend run dev</code> "
            "и откройте http://localhost:5173.</p>")
