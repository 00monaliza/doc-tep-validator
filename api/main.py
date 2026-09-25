"""MVP web service: upload a document package, get a TEP cross-check report.

Run:  uv run uvicorn api.main:app --reload     then open http://127.0.0.1:8000

POST /api/checks                    multipart `files` (PDF/DOCX) -> {id, status}
GET  /api/checks/{id}               status + report when done
GET  /api/checks/{id}/files/{name}  uploaded file (for the in-browser PDF viewer)
POST /api/demo/{lang}               run on the bundled synthetic sample (ru|kz)
"""

from __future__ import annotations

import json
import re
import shutil
import traceback
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

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

app = FastAPI(title="ТЭП-валидатор", version="0.1.0")


def _check_dir(check_id: str) -> Path:
    if not ID_RE.match(check_id):
        raise HTTPException(404, "check not found")
    d = UPLOADS / check_id
    if not d.is_dir():
        raise HTTPException(404, "check not found")
    return d


def _write_status(d: Path, status: str, **extra) -> None:
    (d / "status.json").write_text(json.dumps({"status": status} | extra, ensure_ascii=False), encoding="utf-8")


def _run(d: Path) -> None:
    try:
        files = sorted(p for p in (d / "files").iterdir() if p.suffix.lower() in ALLOWED)
        report = analyze_package(files)
        for doc in report["documents"]:
            doc.pop("path", None)  # do not leak server paths
        (d / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_status(d, "done")
    except Exception as e:  # noqa: BLE001 — surface any analysis failure to the client
        _write_status(d, "error", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc(limit=3))


def _new_check() -> tuple[str, Path]:
    check_id = uuid.uuid4().hex
    d = UPLOADS / check_id
    (d / "files").mkdir(parents=True)
    _write_status(d, "pending")
    return check_id, d


@app.post("/api/checks")
async def create_check(files: list[UploadFile], background: BackgroundTasks) -> dict:
    if not files or len(files) > MAX_FILES:
        raise HTTPException(400, f"upload 1–{MAX_FILES} files")
    check_id, d = _new_check()
    for f in files:
        name = Path(f.filename or "").name
        if Path(name).suffix.lower() not in ALLOWED:
            shutil.rmtree(d)
            raise HTTPException(400, f"{name!r}: only PDF and DOCX are accepted")
        data = await f.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            shutil.rmtree(d)
            raise HTTPException(413, f"{name!r} is larger than {MAX_FILE_BYTES // 2**20} MB")
        (d / "files" / name).write_bytes(data)
    background.add_task(_run, d)
    return {"id": check_id, "status": "pending"}


@app.post("/api/demo/{lang}")
def demo(lang: str, background: BackgroundTasks, kind: str = "text") -> dict:
    if lang not in ("ru", "kz") or kind not in ("text", "scan"):
        raise HTTPException(404, "unknown demo")
    check_id, d = _new_check()
    for src in sorted((SAMPLES / lang / f"{lang}_00001" / kind).glob("*.pdf")):
        shutil.copy(src, d / "files" / src.name)
    background.add_task(_run, d)
    return {"id": check_id, "status": "pending"}


@app.get("/api/checks/{check_id}")
def get_check(check_id: str) -> dict:
    d = _check_dir(check_id)
    status = json.loads((d / "status.json").read_text(encoding="utf-8"))
    status.pop("trace", None)
    if status["status"] == "done":
        status["report"] = json.loads((d / "report.json").read_text(encoding="utf-8"))
    return {"id": check_id} | status


@app.get("/api/checks/{check_id}/files/{name}")
def get_file(check_id: str, name: str) -> FileResponse:
    path = _check_dir(check_id) / "files" / Path(name).name
    if not path.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(path)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "discrepancy_types": [t.value for t in DiscrepancyType],
            "backbones": {lang: b.hub_id for lang, b in BACKBONES.items()}}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")
