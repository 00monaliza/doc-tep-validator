"""Static demo report for the landing page and /demo (no login, no API): report.json + the PDFs it cites.

Run after changes to the pipeline:  uv run python scripts/export_demo.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.main import default_title  # noqa: E402
from src.pipeline import analyze_package  # noqa: E402

SAMPLE = ROOT / "data" / "synthetic" / "samples" / "ru" / "ru_00001" / "text"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "frontend" / "public" / "demo-data")
    out = ap.parse_args().out
    files = sorted(SAMPLE.glob("*.pdf"))
    report = analyze_package(files)
    for doc in report["documents"]:
        doc.pop("path", None)
    report["title"] = default_title(report, [f.name for f in files])
    (out / "files").mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy(f, out / "files" / f.name)
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"demo: {out} ({len(files)} files, {len(report['findings'])} findings)")


if __name__ == "__main__":
    main()
