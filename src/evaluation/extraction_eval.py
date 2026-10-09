"""Slot-level evaluation of TEP extraction from the ПЗ of synthetic sets.

A slot is (object, field). Building fields belong to buildings (``b1``...);
estimated cost, duration and underground volume are project-level and belong to
``project``. The gold value of a slot is the value the ПЗ states in that
object's table (text mentions may repeat, round or contradict it).

Scoring: a predicted slot is correct if its value equals gold to 1e-6. Wrong
values count as a false positive *and* a false negative; slots of unknown
objects are false positives. Building fields predicted for ``project`` (values
outside any building section) are counted as correct/wrong for the only
building of a single-building set and ignored otherwise (reported separately).

Text extraction is scored on its own: every TEP stated in a sentence of the ПЗ
(field, value as written) against the sentence candidates of the extractor.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from src.evaluation.match import map_objects
from src.ner.common.tep_baseline import PROJECT, Extraction
from src.synthesis.formatting import parse_num

BUILDING_FIELDS = ("floors", "building_area_m2", "total_area_m2", "construction_volume_m3")
PROJECT_FIELDS = ("underground_volume_m3", "estimated_cost_ktg", "construction_duration_months")
FIELDS = BUILDING_FIELDS + PROJECT_FIELDS


def gold_slots(gt: dict) -> dict[tuple[str, str], float]:
    pz = gt["tep"]["PZ"]
    slots: dict[tuple[str, str], float] = {}
    if gt.get("profile", "v1") != "v1":
        for bid, o in gt["objects"].items():
            for f in BUILDING_FIELDS:
                if o["tep"].get(f) is not None:
                    slots[(bid, f)] = float(o["tep"][f])
    else:
        for f in BUILDING_FIELDS:
            if f in pz and pz[f]["value"] is not None:
                slots[("b1", f)] = float(pz[f]["value"])
    for f in PROJECT_FIELDS:
        if f in pz and pz[f]["value"] is not None:
            slots[(PROJECT, f)] = float(pz[f]["value"])
    return slots


def gold_text(gt: dict) -> list[tuple[str, str, float]]:
    """(object or '', field, value as written) of every TEP stated in a ПЗ sentence."""
    out = []
    for f, entry in gt["tep"]["PZ"].items():
        for a in entry["anchors"]:
            if "context" in a and f in FIELDS:
                out.append(("", f, parse_num(a["text"])))
    for rec in gt["discrepancies"] + gt["consistent_checks"]:
        for r in rec["refs"]:
            if r.get("place") == "engineering_text":
                out.append((r["object"], r["field"], float(r["value"])))
    for bid, o in gt["objects"].items():
        if o.get("axes_m"):  # "<name>: здание N-этажное ... в осях"
            out.append((bid, "floors", float(o["tep"]["floors"])))
    return list(dict.fromkeys(out))


@dataclass
class Scores:
    tp: Counter = field(default_factory=Counter)
    fp: Counter = field(default_factory=Counter)
    fn: Counter = field(default_factory=Counter)
    ignored: int = 0

    def add(self, pred: dict[tuple[str, str], float], gold: dict[tuple[str, str], float]) -> None:
        for slot, value in pred.items():
            f = slot[1]
            if slot in gold and abs(gold[slot] - value) < 1e-6:
                self.tp[f] += 1
            else:
                self.fp[f] += 1
        for slot in gold:
            if slot not in pred or abs(pred[slot] - gold[slot]) >= 1e-6:
                self.fn[slot[1]] += 1

    def prf(self, f: str | None = None) -> tuple[float, float, float, int]:
        tp = sum(self.tp.values()) if f is None else self.tp[f]
        fp = sum(self.fp.values()) if f is None else self.fp[f]
        fn = sum(self.fn.values()) if f is None else self.fn[f]
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        return p, r, f1, tp + fn


def predicted_slots(ex: Extraction, gt: dict, gold: dict) -> tuple[dict[tuple[str, str], float], int]:
    gt_names = {bid: o["name"] for bid, o in gt["objects"].items()} | {PROJECT: ""}
    omap = map_objects(ex.objects, gt_names)
    buildings = {b for b, _ in gold if b != PROJECT} or {"b1"}
    pred: dict[tuple[str, str], tuple[tuple, float]] = {}
    ignored = 0
    for (obj, f), c in ex.slots.items():
        if f not in FIELDS:
            continue
        if f in PROJECT_FIELDS:
            target = PROJECT
        elif obj == PROJECT:
            if len(buildings) != 1:
                ignored += 1
                continue
            target = next(iter(buildings))
        else:
            target = omap.get(obj, f"?{obj}")
        slot = (target, f)
        if slot not in pred or c.rank < pred[slot][0]:
            pred[slot] = (c.rank, c.value)
    return {s: v for s, (_, v) in pred.items()}, ignored


def real_verdicts(ex: Extraction, ann) -> list[tuple[str, str, float, str]]:
    """(object, field, table value, 'ok' | 'missing' | 'wrong (<v>)') for every TEP of an annotated real ПЗ."""
    omap = map_objects(ex.objects, ann.objects)
    pred = {(omap.get(o, o), f): c.value for (o, f), c in ex.slots.items()}
    out = []
    for obj, fields in ann.tep.items():
        for f, gold in fields.items():
            if f in ("page", "axes_m") or obj not in ("abk", "ceh") and f not in FIELDS:
                continue
            table_value = gold[0] if isinstance(gold, list) else gold  # first listed = table value
            got = pred.get((obj, f))
            verdict = "missing" if got is None else "ok" if abs(got - table_value) < 1e-6 else f"wrong ({got:g})"
            out.append((obj, f, table_value, verdict))
    return out


def text_scores(ex: Extraction, gt: dict) -> tuple[Counter, Counter, Counter, list[bool]]:
    """Per field tp/fp/fn of sentence extraction (field + value), and object correctness of matched mentions."""
    gold = gold_text(gt)
    gt_names = {bid: o["name"] for bid, o in gt["objects"].items()} | {PROJECT: ""}
    omap = map_objects(ex.objects, gt_names)
    remaining = defaultdict(list)
    for obj, f, v in gold:
        remaining[(f, round(v, 6))].append(obj)
    tp, fp, fn, obj_ok = Counter(), Counter(), Counter(), []
    for c in ex.candidates:
        if c.source != "text" or c.field not in FIELDS:
            continue
        key = (c.field, round(c.value, 6))
        if remaining[key]:
            gobj = remaining[key].pop(0)
            tp[c.field] += 1
            if gobj:
                obj_ok.append(omap.get(c.object, c.object) == gobj)
        else:
            fp[c.field] += 1
    for (f, _), objs in remaining.items():
        fn[f] += len(objs)
    return tp, fp, fn, obj_ok
