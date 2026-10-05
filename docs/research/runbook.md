# Порядок запуска экспериментов

Перед первым запуском E2/E3 на финальных seeds заморозьте код: коммит с тегом `protocol-v1`. После заморозки
правила, `match.py` и `protocol.py` не меняются; иначе поднимите `PROTOCOL_VERSION` и перезапустите всё.
Пробные запуски делайте на других seeds: `--seeds 41-45` (без `--seeds` берутся финальные 8000–8099).

| Шаг | Команда | Результат |
|---|---|---|
| E1 | `uv run python scripts/exp_e1_ceiling.py` | `build/research/e1_ceiling.json` |
| E2 | `uv run python scripts/exp_e2_gap.py` (потом разметить промахи в `annotations/real/misses/<id>.json` и запустить снова) | `build/research/e2_gap.json` |
| E3 | `uv run python scripts/exp_e3_compare.py --systems S1 L1 H1 --runs 3` | `build/research/e3_compare.json` |
| E3 (грубая метрика) | то же с `--granularity type` | отдельный прогон, кэш LLM переиспользуется |
| E4 | `uv run python scripts/exp_e4_prepare.py`, затем ручной прогон по `docs/research/e4-protocol.md` | `build/research/e4/observations.csv` |

L1 и H1 требуют `ANTHROPIC_API_KEY` (или `ANTHROPIC_AUTH_TOKEN`) в окружении; без него скрипт E3 завершается с
понятным сообщением. Модель, effort и версия промпта зафиксированы в `src/evaluation/protocol.py`. Ответы
кэшируются в `build/research/llm_cache/`, повторный запуск бесплатен. Файлы в `build/` не коммитятся.
Таблицы для текста диплома берутся из JSON и stdout этих скриптов.

Перед текстом диплома в разделе методологии нужно раскрыть: на финальных seeds 8000–8004 один раз запускался пробный
прогон E2 (только S1, без каких-либо изменений правил).
