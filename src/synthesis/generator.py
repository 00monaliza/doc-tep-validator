"""Generate one linked document set (ПЗ + АР + КР + смета) with ground truth.

RU and KZ sets are *parallel*, not translations: each language draws its own
object, numbers and phrasing from a language-specific RNG stream, while the
ground-truth JSON has exactly the same structure and discrepancy taxonomy.

Profiles: ``v1`` is the original single-building set (the MVP pipeline is built
for it). ``v2`` (default) keeps everything of v1 for the primary building ``b1``
and adds what real explanatory notes look like: 1–3 buildings in the ПЗ, the
same TEP repeated in several sections, label synonyms, mixed number formats,
column orders and broken header words, plus three more discrepancy types. All
v2 variation comes from a separate RNG stream, so ``b1`` values of a seed are
identical in both profiles.

``v3-dev`` / ``v3-test`` are v2 with the TEP labels, unit spellings and some
sentences of the ПЗ taken from ``data/heldout.py`` (about one label in five with
an OCR-like defect). Their choices come from a third RNG stream, so values,
buildings and discrepancies of a seed are those of v2: only the wording differs.

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

from src.ner.common.taxonomy import (
    SYNTHETIC_TYPES_V1,
    SYNTHETIC_TYPES_V2_EXTRA,
    TYPE_LEVEL,
    DiscrepancyType,
    Section,
)
from src.synthesis import templates_kz, templates_ru
from src.synthesis.context import Ctx, Meta
from src.synthesis.data import kz_lexicon, ru_lexicon
from src.synthesis.data.heldout import HELDOUT
from src.synthesis.document import Document
from src.synthesis.pz_objects import names
from src.synthesis.render import render_docx, render_pdf
from src.synthesis.scan import make_scan
from src.synthesis.values import PzPlan, generate_values, plan_objects

SCHEMA_VERSION = "1.2"  # 1.1: documents[].tables, paragraph anchor context; 1.2: objects, profile v2
PROFILES = ("v1", "v2", "v3-dev", "v3-test")
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
    """Attach `tep_ref` pointers and document anchors to every ref of a v1 check (all about b1)."""
    for rec in records:
        rec["object"] = "b1"
        for ref in rec["refs"]:
            ref["object"] = "b1"
            ref["tep_ref"] = f"{ref['section']}.{ref['field']}"
            ref["anchors"] = tep[ref["section"]][ref["field"]]["anchors"]
    return records


def _enrich_plan(records: list[dict], pz: Document) -> list[dict]:
    """Attach ПЗ anchors to the refs of v2 checks (refs point at `mention` keys)."""
    for rec in records:
        for ref in rec["refs"]:
            ref["anchors"] = [a.to_json() for a in pz.anchors[ref["mention"]]]
    return records


def _check_plan_anchored(plan: PzPlan, pz: Document) -> None:
    for key in plan.values:
        if not pz.anchors.get(key):
            raise AssertionError(f"PZ mention {key} is not anchored in the document")


def _objects_json(lang: str, plan: PzPlan | None, meta: Meta) -> dict:
    if plan is None:
        return {"b1": {"name": meta.object_name, "primary": True}}
    lex = kz_lexicon if lang == "kz" else ru_lexicon
    out = {}
    for b in plan.buildings:
        nom, gen = names(lex, b)
        out[b.id] = {"name": nom, "name_gen": gen, "kind": b.kind, "primary": b.primary, "tep": b.tep,
                     "axes_m": list(b.axes_m) if b.axes_m else None, "fire_resistance": b.fire_resistance,
                     "responsibility": b.responsibility}
    return out


def _number(records: list[dict], prefix: str) -> list[dict]:
    for i, rec in enumerate(records, start=1):
        rec["id"] = f"{prefix}{i}"
        rec["level"] = TYPE_LEVEL[DiscrepancyType(rec["type"])].value
    return records


def generate_set(lang: str, seed: int, out_root: Path, inject: set[DiscrepancyType] | None = None,
                 scans: bool = True, profile: str = "v2") -> Path:
    assert lang in LANGS and profile in PROFILES
    rng = random.Random(f"{lang}:{seed}")
    vrng = random.Random(f"{lang}:{seed}:v2") if profile != "v1" else None  # v3 = v2 + held-out wording
    heldout = HELDOUT[lang][profile.removeprefix("v3-")] if profile.startswith("v3-") else None
    hrng = random.Random(f"{lang}:{seed}:v3") if heldout else None
    if inject is None:  # random subset; an empty set yields a fully consistent (negative) sample
        inject = {t for t in SYNTHETIC_TYPES_V1 if rng.random() < 0.5}
        if vrng is not None:
            inject |= {t for t in SYNTHETIC_TYPES_V2_EXTRA if vrng.random() < 0.5}
    elif profile == "v1" and not inject <= set(SYNTHETIC_TYPES_V1):
        raise ValueError(f"profile v1 cannot inject {sorted(inject - set(SYNTHETIC_TYPES_V1))}")

    values = generate_values(rng, inject)
    meta = _meta(lang, rng, values.building_type, values.capacity)
    plan = plan_objects(vrng, values, inject) if vrng is not None else None
    ctx = Ctx(lang, values, meta, random.Random(rng.getrandbits(32)), plan, vrng, heldout, hrng)
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
                 "docx": str(docx_path.relative_to(set_dir)), "tables": doc.tables()}
        if scans:
            scan_pdf = set_dir / "scan" / f"{sec}.pdf"
            pages, params = make_scan(pdf, scan_pdf, scan_rng)
            entry |= {"scan_pdf": str(scan_pdf.relative_to(set_dir)),
                      "scan_pages": [str(p.relative_to(set_dir)) for p in pages], "scan_params": params}
        documents[sec] = entry

    tep = _tep_json(ctx, docs)
    lex = kz_lexicon if lang == "kz" else ru_lexicon
    discrepancies = _enrich(values.discrepancies, tep)
    checks = _enrich(values.consistent_checks, tep)
    if plan is not None:
        _check_plan_anchored(plan, docs["PZ"])
        discrepancies += _enrich_plan(plan.discrepancies, docs["PZ"])
        checks += _enrich_plan(plan.consistent_checks, docs["PZ"])
    gt = {
        "schema_version": SCHEMA_VERSION,
        "profile": profile,
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
        "objects": _objects_json(lang, plan, meta),
        "site": {"seismicity_points": plan.seismicity} if plan else {},
        "tep": tep,
        "discrepancies": _number(discrepancies, "D"),
        "consistent_checks": _number(checks, "C"),
    }
    (set_dir / "ground_truth.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
    return set_dir


__all__ = ["generate_set", "LANGS", "Section"]
