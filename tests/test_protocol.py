from src.evaluation import protocol


def test_final_and_e4_seeds_do_not_overlap_seen_ranges():
    final = set(protocol.seed_list(protocol.FINAL_SEEDS)) | set(protocol.seed_list(protocol.E4_SEEDS))
    for span in protocol.SEEN_SEEDS:
        assert final.isdisjoint(protocol.seed_list(span))


def test_final_and_e4_are_disjoint_and_sized():
    final = protocol.seed_list(protocol.FINAL_SEEDS)
    e4 = protocol.seed_list(protocol.E4_SEEDS)
    assert len(final) == 100 and len(e4) == 20
    assert set(final).isdisjoint(e4)


def test_llm_settings_are_pinned():
    assert protocol.LLM_MODEL and protocol.PROMPT_VERSION and protocol.LLM_RUNS >= 3


def test_resolve_seeds_defaults_to_final_and_accepts_a_span():
    assert protocol.resolve_seeds(None) == protocol.seed_list(protocol.FINAL_SEEDS)
    assert protocol.resolve_seeds("31-33") == [31, 32, 33]
    assert protocol.resolve_seeds("7") == [7]


def test_result_name_marks_smoke_runs():
    assert protocol.result_name("e3_compare", None, 100) == "e3_compare.json"
    assert protocol.result_name("e3_compare", "41-43", 100) == "e3_compare.smoke.json"
    assert protocol.result_name("e3_compare", None, 3) == "e3_compare.smoke.json"
