# Automated extraction and cross‑checking of technical and economic indicators in the text sections of project documentation based on NLP.

Дипломный проект: извлечение ТЭП из текстовых и табличных частей проектной документации
на **русском и казахском** языках и поиск несоответствий между разделами
(ПЗ, текстовая часть АР, текстовая часть КР, сметная документация).

## Быстрый старт

```bash
uv sync                                   # Python 3.12 + зависимости в .venv
./scripts/fetch_assets.sh                 # шрифты DejaVu + tessdata rus/kaz (не в git)
uv run python scripts/check_env.py        # smoke-тест окружения
uv run pytest                             # тесты генератора
uv run python scripts/generate_synthetic.py --lang ru kz --seeds 1-100   # корпус
```

Системный OCR для русского и казахского (рекомендуется; без него используется
локальная копия `assets/tessdata/`):

```bash
brew install tesseract-lang
```

## Структура

```
src/
  ingestion/common/    PDF (pdfplumber, PyMuPDF), DOCX, Tesseract-обёртка
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
scripts/                 check_env.py, generate_synthetic.py, fetch_assets.sh
api/                     FastAPI-заготовка (/health)
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

## Известные ограничения окружения

- **EasyOCR 1.7.2 не поддерживает казахский**: кода `kk`/`kaz` нет в `all_lang_list`.
  Казахский OCR идёт только через Tesseract `kaz`.
- Tesseract `rus`/`kaz` не распознаёт `²`/`³`: «м²» читается как «м?» или «м2».
  В OCR-пути нужна нормализация единиц.
- natasha импортирует `pkg_resources`, поэтому setuptools закреплён на `<81`.
