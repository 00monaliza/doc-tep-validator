from src.evaluation.bench import Scoreboard, gt_slots, score_set, slot

AREA = "AREA_PZ_VS_AR_EXPLICATION"
TOTAL = "TABLE_TOTAL_MISMATCH"
STMT = "STATEMENT_CONTRADICTION"


def test_slot_drops_field_for_slot_free_types_and_local_qty_prefix():
    assert slot(AREA, "total_area_m2") == (AREA, "")
    assert slot("MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE", "local_qty.rebar_a500c_t") == (
        "MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE", "rebar_a500c_t")


def test_gt_slots_reads_discrepancies():
    gt = {"discrepancies": [{"type": AREA, "field": "x"}, {"type": TOTAL, "field": "t1"}]}
    assert gt_slots(gt) == {(AREA, ""), (TOTAL, "t1")}


def test_score_set_counts_tp_fp_fn_by_type():
    rec = score_set("ru", "s1", {(AREA, ""), (TOTAL, "t1")}, {(AREA, ""), (TOTAL, "t2")})
    assert (rec.tp[AREA], rec.fp[TOTAL], rec.fn[TOTAL]) == (1, 1, 1)


def test_type_granularity_ignores_field():
    rec = score_set("ru", "s1", {(TOTAL, "t1")}, {(TOTAL, "t2")}, granularity="type")
    assert rec.tp[TOTAL] == 1 and not rec.fp and not rec.fn


def test_negative_set_has_false_positive_and_no_recall():
    board = Scoreboard()
    board.add(score_set("ru", "neg", set(), {(AREA, "")}))
    p, r, f = board.prf()
    assert (p, r, f) == (0.0, None, None)
    assert board.fp_per_set() == 1.0


def test_same_slot_predicted_twice_counts_once():
    got = [(AREA, ""), (AREA, "")]
    rec = score_set("ru", "s", {(AREA, "")}, set(got))
    assert rec.tp[AREA] == 1 and not rec.fp


def test_prf_by_level_and_language():
    board = Scoreboard()
    board.add(score_set("ru", "a", {(AREA, "")}, {(AREA, "")}))  # numeric tp
    board.add(score_set("kz", "b", {(STMT, "f")}, set()))  # logical fn
    assert board.prf(level="numeric")[1] == 1.0
    assert board.prf(level="logical")[1] == 0.0
    assert board.prf(lang="kz", level="numeric") == (None, None, None)


def test_bootstrap_interval_brackets_point_estimate_and_is_reproducible():
    board = Scoreboard()
    for i in range(30):
        got = {(AREA, "")} if i % 3 else set()
        board.add(score_set("ru", f"s{i}", {(AREA, "")}, got))
    lo, hi = board.bootstrap_f1(iters=200, seed=0)
    assert lo <= board.prf()[2] <= hi
    assert (lo, hi) == board.bootstrap_f1(iters=200, seed=0)


def test_bootstrap_returns_none_without_data():
    assert Scoreboard().bootstrap_f1() is None
