"""Generate one linked document set (ПЗ + АР + КР + смета) with ground truth.

RU and KZ sets are *parallel*, not translations: each language draws its own
object, numbers and phrasing from a language-specific RNG stream, while the
ground-truth JSON has exactly the same structure and discrepancy taxonomy.

Output layout for set `<lang>_<seed>`:

    <out>/<lang>/<set_id>/
        text/{PZ,AR,KR,SMETA}.pdf   text-layer PDF (fpdf2, DejaVu Sans)
        text/{PZ,AR,KR,SMETA}.docx  same content as DOCX
        scan/{PZ,AR,KR,SMETA}.pdf   image-only PDF with scan noise
        scan/<SEC>_p<N>.jpg         the page images of that PDF
        ground_truth.json
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict
from pathlib import Path

from faker import Faker

from src.ner.common.taxonomy import DiscrepancyType, Section
from src.synthesis import templates_kz, templates_ru
from src.synthesis.context import Ctx, Meta
from src.synthesis.data import kz_lexicon, ru_lexicon
from src.synthesis.document import Document
from src.synthesis.render import render_docx, render_pdf
from src.synthesis.scan import make_scan
from src.synthesis.values import generate_values

SCHEMA_VERSION = "1.0"
YEAR = 2026
LANGS = ("ru", "kz")
BUILDERS = {"ru": templates_ru.BUILDERS, "kz": templates_kz.BUILDERS}


def unit_of(fld: str) -> str:
    for suffix, unit in (("_ktg", "kKZT"), ("_tg", "KZT"), ("_pct", "%"), ("_m2", "m2"), ("_m3", "m3"),
                         ("_t", "t"), ("_months", "month"), ("floors", "floor")):
        if fld.endswith(suffix) or fld.split(".")[0].endswith(suffix):
            return unit
    raise ValueError(f"no unit for {fld}")


def _meta(lang: str, rng: random.Random, building_type: str, capacity: int) -> Meta:
    if lang == "kz":
        lex = kz_lexicon
        city = rng.choice(lex.CITIES)
        address = f"{city} қ., {rng.choice(lex.STREETS)}, {rng.randint(1, 180)}"
        chief = f"{rng.choice(lex.SURNAMES)} {rng.choice(lex.INITIALS)} {rng.choice(lex.INITIALS)}"
    else:
        lex = ru_lexicon
        fake = Faker("ru_RU")
        fake.seed_instance(rng.getrandbits(32))
        city = rng.choice(lex.CITIES)
        address = f"г. {city}, {rng.choice(lex.STREETS)}, {rng.randint(1, 180)}"
        chief = f"{fake.last_name_male()} {fake.first_name_male()[0]}. {fake.middle_name_male()[0]}."
    return Meta(
        object_name=lex.BUILDING_NAMES[building_type].format(n=capacity),
        city=city, address=address,
        customer=rng.choice(lex.CUSTOMERS).format(city=city),
        designer=rng.choice(lex.DESIGNERS),
        chief_engineer=chief,
        project_code=f"{rng.randint(100, 999)}-{YEAR}",
        year=YEAR,
    )


def _tep_json(ctx: Ctx, docs: dict[str, Document]) -> dict:
    out: dict[str, dict] = {}
    for section, fields in ctx.v.tep.items():
        anchors = docs[section.value].anchors
        sec_out = {}
        for fld, value in fields.items():
            found = [a.to_json() for a in anchors.get(fld, [])]
            if value is not None and not found:
                raise AssertionError(f"{section}.{fld} has a value but is not anchored in the document")
            if value is None and found:
                raise AssertionError(f"{section}.{fld} is marked missing but appears in the document")
            sec_out[fld] = {"value": value, "unit": unit_of(fld), "present": value is not None,
                            "anchors": found}
        out[section.value] = sec_out
    # rooms are anchored individually in the AR explication
    for r in ctx.v.rooms:
        fld = f"room.{r.number}.area_m2"
        out["AR"][fld] = {"value": r.area_m2, "unit": "m2", "present": True,
                          "anchors": [a.to_json() for a in docs["AR"].anchors[fld]]}
    return out


def _enrich(records: list[dict], tep: dict) -> list[dict]:
    """Attach `tep_ref` pointers and document anchors to every ref of a check."""
    for rec in records:
        for ref in rec["refs"]:
            ref["tep_ref"] = f"{ref['section']}.{ref['field']}"
            ref["anchors"] = tep[ref["section"]][ref["field"]]["anchors"]
    return records


def generate_set(lang: str, seed: int, out_root: Path, inject: set[DiscrepancyType] | None = None,
                 scans: bool = True) -> Path:
    assert lang in LANGS
    rng = random.Random(f"{lang}:{seed}")
    if inject is None:  # random subset; an empty set yields a fully consistent (negative) sample
        inject = {t for t in DiscrepancyType if rng.random() < 0.5}

    values = generate_values(rng, inject)
    meta = _meta(lang, rng, values.building_type, values.capacity)
    ctx = Ctx(lang, values, meta, random.Random(rng.getrandbits(32)))
    docs = {sec: build(ctx) for sec, build in BUILDERS[lang].items()}

    set_id = f"{lang}_{seed:05d}"
    set_dir = out_root / lang / set_id
    (set_dir / "text").mkdir(parents=True, exist_ok=True)
    (set_dir / "scan").mkdir(parents=True, exist_ok=True)
    scan_rng = random.Random(rng.getrandbits(32))

    documents = {}
    for sec, doc in docs.items():
        pdf, docx_path = set_dir / "text" / f"{sec}.pdf", set_dir / "text" / f"{sec}.docx"
        render_pdf(doc, pdf)
        render_docx(doc, docx_path)
        entry = {"code": doc.code, "title": doc.title, "text_pdf": str(pdf.relative_to(set_dir)),
                 "docx": str(docx_path.relative_to(set_dir))}
        if scans:
            scan_pdf = set_dir / "scan" / f"{sec}.pdf"
            pages, params = make_scan(pdf, scan_pdf, scan_rng)
            entry |= {"scan_pdf": str(scan_pdf.relative_to(set_dir)),
                      "scan_pages": [str(p.relative_to(set_dir)) for p in pages], "scan_params": params}
        documents[sec] = entry

    tep = _tep_json(ctx, docs)
    lex = kz_lexicon if lang == "kz" else ru_lexicon
    gt = {
        "schema_version": SCHEMA_VERSION,
        "set_id": set_id,
        "lang": lang,
        "seed": seed,
        "injected_types": sorted(t.value for t in inject),
        "object": asdict(meta) | {
            "building_type": values.building_type, "capacity": values.capacity, "floors": values.floors,
            "fire_class": values.fire_class, "floor_height_m": values.floor_height_m,
            "has_basement": values.has_basement, "axes_m": list(values.axes_m),
            "foundation_thickness_mm": values.foundation_thickness_mm,
        },
        "documents": documents,
        "ar_explication": [asdict(r) | {"name": lex.ROOMS[r.kind]} for r in values.rooms],
        "tep": tep,
        "discrepancies": _enrich(values.discrepancies, tep),
        "consistent_checks": _enrich(values.consistent_checks, tep),
    }
    (set_dir / "ground_truth.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
    return set_dir


__all__ = ["generate_set", "LANGS", "Section"]
