import json
from types import SimpleNamespace

from src.evaluation.llm import AnthropicClient, LLMSystem, build_prompt, parse_items
from src.synthesis.generator import generate_set

AREA = "AREA_PZ_VS_AR_EXPLICATION"


class FakeClient:
    def __init__(self, reply: str):
        self.reply, self.calls = reply, []

    def complete(self, system: str, user: str, run: int = 0) -> str:
        self.calls.append((system, user, run))
        return self.reply


def test_parse_items_accepts_fenced_json_with_prose_around():
    fence = "`" * 3  # a literal fence would end the markdown block of the plan
    raw = f'Вот результат:\n{fence}json\n[{{"type": "{AREA}", "field": "total_area_m2"}}]\n{fence}\nГотово.'
    items, dropped = parse_items(raw)
    assert [i["type"] for i in items] == [AREA] and dropped == 0


def test_parse_items_drops_unknown_types_and_counts_them():
    raw = json.dumps([{"type": AREA, "field": "x"}, {"type": "NOT_A_TYPE", "field": "y"}, "junk"])
    items, dropped = parse_items(raw)
    assert len(items) == 1 and dropped == 2


def test_parse_items_survives_garbage():
    assert parse_items("совсем не json") == ([], 1)
    assert parse_items("") == ([], 1)


def test_prompt_lists_all_documents_and_allowed_types():
    system, user = build_prompt({"PZ": "текст ПЗ", "AR": "текст АР"})
    assert "=== PZ ===" in user and "текст АР" in user
    assert AREA in system and "STATEMENT_CONTRADICTION" in system


def test_llm_system_returns_slots_and_counts_duplicates_once(tmp_path):
    set_dir = generate_set("ru", 31, tmp_path, scans=False, profile="v1")
    reply = json.dumps([{"type": AREA, "field": "total_area_m2"}, {"type": AREA, "field": "total_area_m2"}])
    system = LLMSystem(FakeClient(reply))
    assert system.detect(sorted(set_dir.glob("text/*.pdf")), "ru") == {(AREA, "")}


def test_llm_system_tracks_parse_failures(tmp_path):
    set_dir = generate_set("ru", 31, tmp_path, scans=False, profile="v1")
    system = LLMSystem(FakeClient("нет ответа"))
    assert system.detect(sorted(set_dir.glob("text/*.pdf")), "ru") == set()
    assert system.parse_failures == 1


def test_llm_system_skips_call_for_documents_without_text(tmp_path):
    set_dir = generate_set("ru", 31, tmp_path, scans=True, profile="v1")
    client = FakeClient("[]")
    system = LLMSystem(client)
    assert system.detect(sorted(set_dir.glob("scan/*.pdf")), "ru") == set()
    assert client.calls == []


def test_valid_empty_answer_is_not_a_parse_failure(tmp_path):
    set_dir = generate_set("ru", 31, tmp_path, scans=False, profile="v1")
    system = LLMSystem(FakeClient("[]"))
    assert system.detect(sorted(set_dir.glob("text/*.pdf")), "ru") == set()
    assert system.parse_failures == 0


def test_parse_items_survives_non_string_type():
    assert parse_items('[{"type": ["X"]}]') == ([], 1)


def test_parse_items_ignores_brackets_in_surrounding_prose():
    raw = f'Нашёл [см. ниже]:\n[{{"type": "{AREA}", "field": "f"}}]\nСм. п. [1].'
    items, dropped = parse_items(raw)
    assert [i["type"] for i in items] == [AREA] and dropped == 0


def test_null_field_becomes_empty_slot(tmp_path):
    set_dir = generate_set("ru", 31, tmp_path, scans=False, profile="v1")
    reply = json.dumps([{"type": "TABLE_TOTAL_MISMATCH", "field": None}])
    got = LLMSystem(FakeClient(reply)).detect(sorted(set_dir.glob("text/*.pdf")), "ru")
    assert got == {("TABLE_TOTAL_MISMATCH", "")}


def make_api(text, stop_reason="end_turn"):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop_reason)

    return SimpleNamespace(messages=SimpleNamespace(create=create)), calls


def test_client_caches_complete_answers_and_reuses_them(tmp_path):
    api, calls = make_api("[]")
    client = AnthropicClient(cache_dir=tmp_path, api=api)
    assert client.complete("s", "u") == "[]" and client.complete("s", "u") == "[]"
    assert len(calls) == 1 and calls[0]["output_config"] == {"effort": client.effort}


def test_client_does_not_cache_truncated_answers(tmp_path):
    api, calls = make_api("[{", stop_reason="max_tokens")
    client = AnthropicClient(cache_dir=tmp_path, api=api)
    client.complete("s", "u")
    client.complete("s", "u")
    assert len(calls) == 2 and client.uncached == 2


def test_cache_key_includes_max_tokens(tmp_path):
    api, calls = make_api("[]")
    AnthropicClient(cache_dir=tmp_path, api=api, max_tokens=100).complete("s", "u")
    AnthropicClient(cache_dir=tmp_path, api=api, max_tokens=200).complete("s", "u")
    assert len(calls) == 2
