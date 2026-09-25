# Automated extraction and cross‑checking of technical and economic indicators in the text sections of project documentation based on NLP.

Дипломный проект: извлечение ТЭП из текстовых и табличных частей проектной документации
на **русском и казахском** языках и поиск несоответствий между разделами
(ПЗ, текстовая часть АР, текстовая часть КР, сметная документация).

## Быстрый старт

```bash
uv sync                                   # Python 3.12 + зависимости в .venv
brew install tesseract-lang                # Tesseract rus + kaz (обязательно)
uv run python scripts/check_env.py        # smoke-тест окружения
uv run pytest                             # тесты генератора
uv run python scripts/generate_synthetic.py --lang ru kz --seeds 1-100   # корпус
```

## MVP: веб-сервис сверки ТЭП

```bash
uv run uvicorn api.main:app --port 8000     # затем открыть http://127.0.0.1:8000
```

Пользователь загружает пакет (ПЗ, АР, КР, смета; PDF или DOCX; RU или KZ) и получает отчёт с тремя вкладками:

- **Замечания** — расхождения и отсутствующие ТЭП, клик открывает страницу PDF с обведённым значением;
- **ТЭП** — все найденные показатели по разделам;
- **Комплектность** — какие из 4 разделов загружены.

Для быстрой проверки есть кнопки с примерами на русском, казахском и примером-сканом.

Конвейер ([src/pipeline.py](src/pipeline.py)):
`layout.py` (текст и таблицы pdfplumber с координатами, склейка таблиц между страницами)
→ `classify.py` (язык по служебным словам, раздел по заголовку или шифру)
→ `ner/common/rules.py` (извлечение по правилам, шаблоны `ner/ru|kz/rules.py`)
→ `crossvalidation/engine.py` (4 типа проверок с допусками из `taxonomy.py`)
→ `api/` (FastAPI + одностраничный интерфейс, pdf.js с CDN).

Оценка `scripts/eval_pipeline.py` на новых синтетических наборах (seeds 1000–1099, 2000–2009):

| Вход | Извлечение ТЭП | Обнаружение несоответствий (P / R) |
|---|---|---|
| PDF с текстом, RU/KZ | 100 % | 100 % / 100 % по всем 4 типам |
| DOCX, RU/KZ | 100 % | 100 % / 100 % |
| Сканы, RU/KZ | 9–13 % | низкие; отсутствие ТЭП по сканам не проверяется |

100 % на синтетике означает только, что конвейер собран без ошибок: правила и генератор описывают
одну и ту же структуру документов. Качество на реальных проектах пока неизвестно, это главный
открытый вопрос. Сканы в MVP поддерживаются экспериментально: находки со скана помечаются
«сверьте вручную». Следующий шаг OCR-пути — распознавание таблиц по ячейкам.

## Структура

```
src/
  ingestion/common/    PDF (pdfplumber, PyMuPDF), DOCX, Tesseract-обёртка,
                       normalize.py — восстановление м²/м³ после OCR
  synthesis/           генератор синтетических наборов
    values.py          ТЭП и внесение несоответствий (не зависит от языка)
    templates_ru/      шаблоны ПЗ/АР/КР/смета на русском
    templates_kz/      шаблоны на казахском (параллельные, не перевод)
    data/              лексиконы (kz_lexicon.py, ru_lexicon.py)
    render.py, scan.py PDF/DOCX-рендер (fpdf2) и имитация скана (Pillow)
  ner/{ru,kz}/         будущие baseline и модели
  ner/common/          taxonomy.py (разделы, поля ТЭП, типы несоответствий, допуски), models.py
  crossvalidation/, evaluation/
data/synthetic/{ru,kz}/  сгенерированные корпуса (в .gitignore)
data/synthetic/samples/  пробные наборы ru_00001, kz_00001 (в git)
data/real/               реальные документы (пусто)
scripts/                 check_env.py, generate_synthetic.py, eval_ocr_units.py, fetch_assets.sh
api/                     FastAPI + static/index.html (интерфейс)
```

## Синтетические данные

Один набор включает 4 документа (ПЗ, АР, КР, смета, где смета = ЛС 02-01-01 + ОС 02-01 + ССР).
Каждый документ есть в трёх видах: `text/*.pdf` (с текстовым слоем), `text/*.docx`, `scan/*.pdf`
(только изображение: перекос ±1,2°, размытие, гауссов шум, пятна, JPEG).
Русский и казахский наборы параллельные: объект, числа и формулировки у каждого языка
берутся из своего потока RNG, а структура `ground_truth.json` одна и та же.

Типы несоответствий (`src/ner/common/taxonomy.py`):

| Тип | Что сравнивается | Допуск MATCH |
|---|---|---|
| `AREA_PZ_VS_AR_EXPLICATION` | ПЗ `total_area_m2` ↔ сумма экспликации АР | 0,5 % |
| `MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE` | КР объём материала ↔ количество в ЛС | 1 % |
| `COST_OBJECT_ESTIMATE_VS_SUMMARY` | итог ОС 02-01 ↔ строка ОС 02-01 в гл. 2 ССР | 0,001 тыс. тг |
| `MISSING_MANDATORY_TEP` | обязательный ТЭП отсутствует в разделе | — |

`ground_truth.json`: `tep[<раздел>][<поле>]` содержит `value`, `unit`, `present` и `anchors`
(`block_id`, строку и столбец таблицы или абзац, точный текст в документе). В `discrepancies[]`
и `consistent_checks[]` лежат `refs` с `tep_ref` (например, `SMETA.local_qty.rebar_a500c_t`) и теми же
якорями. `delta_rel` считается относительно второй ссылки. Коды нормативов в ЛС
(`Е06-01-001-01` и т. п.) выдуманы и служат только заполнителями.

## Модели (проверено через HuggingFace Hub API 2026-09-25)

| Язык | Модель | Статус |
|---|---|---|
| RU | [`cointegrated/rubert-tiny2`](https://huggingface.co/cointegrated/rubert-tiny2) (MIT) | основная |
| KZ | [`FacebookAI/xlm-roberta-base`](https://huggingface.co/FacebookAI/xlm-roberta-base) (MIT) | **временный multilingual fallback** |

**kazBERT и kazRoBERTa от ISSAI на Hub не найдены.** В организации `issai` опубликованы LLM
(KazLLM, Qwen-Kazakh, Qolda), TTS и ASR, а из кодировщиков есть только классификатор тональности
`issai/rembert-sentiment-analysis-polarity-classification-kazakh`. Сырого ISSAI-кодировщика для
дообучения NER нет. Кандидаты для сравнения с fallback:

- [`kz-transformers/kaz-roberta-conversational`](https://huggingface.co/kz-transformers/kaz-roberta-conversational):
  одноязычная казахская RoBERTa-base, Apache-2.0. Организация kz-transformers, не ISSAI.
- [`yeshpanovrustem/xlm-roberta-large-kaznerd`](https://huggingface.co/yeshpanovrustem/xlm-roberta-large-kaznerd):
  XLM-R large, дообученная на KazNERD. CC-BY-4.0, 560M параметров.
- Датасет ISSAI [`issai/kaznerd`](https://huggingface.co/datasets/issai/kaznerd) (LREC 2022).

Токенизация строки ТЭП на казахском: у XLM-R и kaz-roberta 0 `[UNK]`, у rubert-tiny2 4 `[UNK]`.
Для RU rubert-tiny2 даёт `[UNK]` на длинном тире «—», поэтому тире нужно нормализовать.

## OCR-путь

Единственный OCR-движок — Tesseract (`rus`, `kaz`). **EasyOCR удалён**: в его кириллических
моделях (`cyrillic_g1/g2`) в алфавите нет Ә ә Ң ң Ұ ұ Һ һ, то есть сеть физически не может их
выдать. Использовать его можно только после собственного дообучения распознавателя, а это вне скоупа.

Tesseract не знает `²`/`³`. На сканах «м²» превращается в `м2`, `м3`, `мз`, `м?`, `м*` или просто `м`,
причём цифре доверять нельзя: у кладки кирпича OCR выдавал `м2`, хотя там м³.
`src/ingestion/common/normalize.py` определяет степень по ближайшему ключевому слову в строке
(площадь/ауданы → м²; объём/көлемі/бетон/кладка/қалау → м³). Цифра из OCR используется
как запасная подсказка, если ключевого слова нет. `мм`, `ММ`, `М200`, W6→`М/6` и метры не трогаются.
Каждое решение пишется в журнал (`context`, `context_overrides_ocr`, `ocr_hint`, `unresolved`).

`scripts/eval_ocr_units.py` сравнивает единицы на скане с текстовым слоем того же документа.
Правила подбирались на наборах seeds 1, 11–15 (dev), честная оценка сделана на невиденных seeds 101–105 (held-out):

| | наивно 2→², 3/з→³ (held-out) | нормализация, held-out | нормализация, dev (оптимистично) |
|---|---|---|---|
| RU | 66,7 % | **90,5 %** (19/21) | 89,7 % (26/29) |
| KZ | 47,6 % | **81,0 %** (17/21) | 92,9 % (26/28) |

Выборка маленькая (около 20 единиц на язык), поэтому доверительный интервал ±10–15 п. п.

Сопоставить удаётся только около 28 % единиц: строки таблиц на скане Tesseract (`--psm 6`) часто
превращает в мусор. Следующий шаг OCR-пути — распознавание таблиц по ячейкам.

## Прочее

- natasha импортирует `pkg_resources`, поэтому setuptools закреплён на `<81`.
