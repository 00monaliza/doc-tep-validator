"""Environment smoke test.

Run:  uv run python scripts/check_env.py
Exit code is non-zero if any REQUIRED check fails. Known limitations
(e.g. EasyOCR without Kazakh) are reported as WARN and do not fail the run.

The PDF round-trip check renders RU and KZ text with reportlab and fpdf2 using
the embedded DejaVu Sans TTF, extracts it back with pdfplumber (text layer) and
Tesseract (rus / kaz), and compares line by line. Lost Kazakh-specific letters
("?", U+FFFD, tofu boxes, or plain absence) fail the check with a message that
names the letters. A negative control renders KZ text with a built-in
(non-Unicode) font and asserts that the checker catches the loss.
"""

from __future__ import annotations

import difflib
import importlib
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BUILD = ROOT / "build" / "check_env"
FONT = ROOT / "assets" / "fonts" / "DejaVuSans.ttf"

KZ_SPECIAL = "ӘәҒғҚқҢңӨөҰұҮүҺһІі"
REPLACEMENT_MARKERS = {"?", "�", "□", "■", "☐"}

TEXT = {
    "ru": [
        "Общая площадь здания — 3 245,60 м²",
        "Строительный объём: 14 820,50 м³",
        "Сметная стоимость строительства: 1 254 300,000 тыс. тенге",
        "Экспликация помещений: вестибюль, коридор, лестничная клетка",
        "Съешь же ещё этих мягких французских булок, да выпей чаю",
    ],
    "kz": [
        "Ғимараттың жалпы ауданы — 3 245,60 м²",
        "Құрылыс көлемі: 14 820,50 м³",
        "Әкімшілік ғимарат, Өскемен қаласы, Жаңа көше",
        "Ұлттық стандарт, Үй-жайлар экспликациясы",
        "Жиһаз орналастыру, Һ әрпі, Іргетас тақтасы",
        "Әә Ғғ Ққ Ңң Өө Ұұ Үү Һһ Іі",
    ],
}

results: list[tuple[str, str, str]] = []  # (status, name, detail)


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    print(f"[{status:4}] {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------- imports
def check_imports() -> None:
    modules = [
        ("pdfplumber", "pdfplumber"), ("pymupdf", "PyMuPDF"), ("docx", "python-docx"),
        ("reportlab", "reportlab"), ("fpdf", "fpdf2"), ("pytesseract", "pytesseract"),
        ("easyocr", "easyocr"), ("natasha", "natasha"), ("torch", "torch"),
        ("transformers", "transformers"), ("datasets", "datasets"), ("pandas", "pandas"),
        ("sklearn", "scikit-learn"), ("faker", "faker"), ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"), ("pydantic", "pydantic"), ("PIL", "Pillow"),
    ]
    for mod, label in modules:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", None) or getattr(m, "VERSION", None) or ""
            if mod == "pymupdf":
                ver = m.VersionBind
            record("OK", f"import {label}", str(ver))
        except Exception as e:  # noqa: BLE001
            record("FAIL", f"import {label}", repr(e))


def check_torch() -> None:
    import torch

    mps = torch.backends.mps.is_available()
    record("OK" if mps else "WARN", "torch.backends.mps.is_available()", str(mps))
    if mps:
        x = torch.ones(3, device="mps") * 2
        record("OK", "tensor op on MPS", str(x.cpu().tolist()))


def check_natasha() -> None:
    from natasha import Doc, MorphVocab, NewsEmbedding, NewsMorphTagger, Segmenter

    doc = Doc("Общая площадь здания составляет 3245,6 квадратных метров.")
    doc.segment(Segmenter())
    doc.tag_morph(NewsMorphTagger(NewsEmbedding()))
    vocab = MorphVocab()
    for t in doc.tokens:
        t.lemmatize(vocab)
    lemmas = " ".join(t.lemma for t in doc.tokens)
    record("OK", "natasha segment+morph+lemma", lemmas)


def check_tesseract() -> None:
    from src.ingestion.common import ocr

    sys_langs = ocr.system_languages()
    record("OK" if sys_langs else "FAIL", "system tesseract languages", ", ".join(sorted(sys_langs)))
    for code in ("rus", "kaz"):
        if code in sys_langs:
            record("OK", f"system tesseract '{code}'")
        else:
            extra = " Kazakh OCR quality will be worse without it." if code == "kaz" else ""
            record("WARN", f"system tesseract '{code}' MISSING",
                   f"install: `{ocr.BREW_INSTALL_HINT}`.{extra}")
        try:
            src = ocr.resolve_language(code)
            record("OK", f"tesseract '{code}' resolved", f"{src.origin} ({src.tessdata_dir or 'default'})")
        except RuntimeError as e:
            record("FAIL", f"tesseract '{code}' unavailable", str(e))


def check_easyocr() -> None:
    import easyocr
    from easyocr.config import all_lang_list

    has_kk = any(c in all_lang_list for c in ("kk", "kaz", "kz"))
    if has_kk:
        record("OK", "easyocr Kazakh language code", f"easyocr {easyocr.__version__}")
    else:
        record("WARN", "easyocr has NO Kazakh language code (known limitation)",
               f"easyocr {easyocr.__version__}; Kazakh OCR goes through Tesseract 'kaz' only")


# ---------------------------------------------------------------- PDF round-trip
def render_reportlab(lines: list[str], path: Path, unicode_font: bool = True) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    font = "Helvetica"
    if unicode_font:
        pdfmetrics.registerFont(TTFont("DejaVuSans", str(FONT)))
        font = "DejaVuSans"
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont(font, 16)
    y = A4[1] - 72
    for line in lines:
        c.drawString(56, y, line)
        y -= 30
    c.save()


def render_fpdf2(lines: list[str], path: Path, unicode_font: bool = True) -> None:
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.add_page()
    if unicode_font:
        pdf.add_font("DejaVuSans", fname=str(FONT))
        pdf.set_font("DejaVuSans", size=16)
    else:
        pdf.set_font("Helvetica", size=16)
    for line in lines:
        pdf.cell(0, 11, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


UNIT_SUPERSCRIPT = re.compile(r"м[²³?23'’]")


def mask_unit_superscripts(text: str) -> str:
    """Tesseract has no '²'/'³' in rus/kaz models and reads 'м²' as 'м?'/'м2'.

    That is a unit-normalisation issue for the extractor, not a glyph loss, so the
    OCR comparison masks it (and reports it separately as WARN).
    """
    return UNIT_SUPERSCRIPT.sub("м#", text)


def compare_lines(expected: list[str], got_text: str, lang: str, strict: bool) -> list[str]:
    """Return a list of human-readable problems (empty = pass)."""
    problems = []
    got = [ln.strip() for ln in got_text.splitlines() if ln.strip()]
    if not strict:
        expected = [mask_unit_superscripts(e) for e in expected]
        got = [mask_unit_superscripts(g) for g in got]
    if lang == "kz":
        wanted = set(KZ_SPECIAL)
        present = set("".join(got))
        lost = sorted(wanted - present, key=KZ_SPECIAL.index)
        if lost:
            problems.append(f"Kazakh letters LOST: {' '.join(lost)}")
    for i, exp in enumerate(expected):
        best = max(got, key=lambda g: difflib.SequenceMatcher(None, exp, g).ratio(), default="")
        ratio = difflib.SequenceMatcher(None, exp, best).ratio()
        markers = {ch for ch in best if ch in REPLACEMENT_MARKERS and ch not in exp}
        if markers:
            problems.append(f"line {i + 1}: replacement glyphs {sorted(markers)} in {best!r}")
        if strict and best != exp:
            problems.append(f"line {i + 1}: expected {exp!r}, got {best!r}")
        elif not strict and ratio < 0.85:
            problems.append(f"line {i + 1}: similarity {ratio:.2f} < 0.85: {best!r}")
    return problems


def check_pdf_roundtrip() -> dict[str, bool]:
    from src.ingestion.common.ocr import ocr_image
    from src.ingestion.common.pdf import extract_text, rasterize

    BUILD.mkdir(parents=True, exist_ok=True)
    if not FONT.exists():
        record("FAIL", "Unicode font", f"{FONT} missing — run scripts/fetch_assets.sh")
        return {}
    engine_ok: dict[str, bool] = {}
    superscript_lost: set[str] = set()
    for engine, render in (("reportlab", render_reportlab), ("fpdf2", render_fpdf2)):
        ok = True
        for lang, lines in TEXT.items():
            pdf_path = BUILD / f"roundtrip_{engine}_{lang}.pdf"
            render(lines, pdf_path)
            problems = compare_lines(lines, extract_text(pdf_path), lang, strict=True)
            name = f"{engine} → pdfplumber [{lang}]"
            record("FAIL" if problems else "OK", name, "; ".join(problems) or "all lines identical")
            ok &= not problems

            ocr_text = ocr_image(rasterize(pdf_path, dpi=300)[0], lang)
            if "²" not in ocr_text and "³" not in ocr_text:
                superscript_lost.add(f"{engine}/{lang}")
            problems = compare_lines(lines, ocr_text, lang, strict=False)
            name = f"{engine} → tesseract '{ 'rus' if lang == 'ru' else 'kaz'}' [{lang}]"
            detail = "; ".join(problems) or "all lines ≥0.85 similar" + (
                ", all 18 Kazakh letters recognised" if lang == "kz" else "")
            record("FAIL" if problems else "OK", name, detail)
            ok &= not problems
        engine_ok[engine] = ok
    if superscript_lost:
        record("WARN", "tesseract reads 'м²'/'м³' as 'м?'/'м2' (known OCR limitation)",
               f"in {', '.join(sorted(superscript_lost))}; normalise units in the OCR extraction path")
    return engine_ok


def check_negative_control() -> None:
    """A built-in Type1 font cannot encode Kazakh letters; the checker must notice."""
    lines = TEXT["kz"]
    from src.ingestion.common.pdf import extract_text

    for engine, render in (("reportlab", render_reportlab), ("fpdf2", render_fpdf2)):
        path = BUILD / f"negative_{engine}_kz.pdf"
        try:
            render(lines, path, unicode_font=False)
            problems = compare_lines(lines, extract_text(path), "kz", strict=True)
            caught = bool(problems)
            detail = problems[0] if problems else "checker did NOT notice the loss"
        except Exception as e:  # noqa: BLE001 — fpdf2 raises on unencodable chars
            caught, detail = True, f"renderer refused: {type(e).__name__}"
        record("OK" if caught else "FAIL", f"negative control: {engine} + built-in Helvetica [kz]", detail)


def main() -> int:
    for step in (check_imports, check_torch, check_natasha, check_tesseract, check_easyocr):
        try:
            step()
        except Exception:  # noqa: BLE001
            record("FAIL", step.__name__, traceback.format_exc(limit=2).strip().splitlines()[-1])
    engine_ok = check_pdf_roundtrip()
    check_negative_control()

    print("\n=== Summary ===")
    for engine, ok in engine_ok.items():
        print(f"  {engine:9}: {'renders RU+KZ correctly' if ok else 'BROKEN for RU/KZ'}")
    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    print(f"  {len(results)} checks, {len(fails)} FAIL, {len(warns)} WARN")
    for _, name, detail in warns:
        print(f"  WARN: {name} — {detail}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
