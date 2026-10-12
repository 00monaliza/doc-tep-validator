import json
import subprocess
import sys


def test_export_demo_writes_report_and_pdfs(tmp_path):
    subprocess.run([sys.executable, "scripts/export_demo.py", "--out", str(tmp_path)], check=True)
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["MISMATCH"] == 3 and report["title"]
    assert all("path" not in d for d in report["documents"])
    assert sorted(p.name for p in (tmp_path / "files").iterdir()) == ["AR.pdf", "KR.pdf", "PZ.pdf", "SMETA.pdf"]
