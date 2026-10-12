# Переделка фронтенда, план 2: лендинг, демо и заявки — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Лендинг на `/` (9 блоков, RU/KZ, 3D-сцена «Расслоение» со скроллом и запасным SVG), демо-отчёт без входа на `/demo` и в блоке 04, заявки «Запросить доступ».

**Architecture:** То же Vite + React приложение, что и в плане 1. Лендинг — ленивый маршрут `/`; сцена — отдельный ленивый чанк (react-three-fiber 8 + drei 9), её состояние считается чистыми функциями от прогресса скролла. Демо — статический отчёт (`frontend/public/demo-data/`), который рисует тот же `ReportBody`, что и платформа, с подменённым источником файлов и сохранением вердиктов. Заявки — публичный эндпоинт FastAPI с хранением в папке или Supabase.

**Tech Stack:** React 18.3, react-router 7, three + @react-three/fiber 8 + @react-three/drei 9, motion 12, Tailwind 4, Vitest, Playwright; FastAPI + pytest.

**Spec:** `docs/superpowers/specs/2026-10-11-frontend-redesign-design.md` — §4 (лендинг), §6 (демо без входа, заявки), §7 (бюджеты, доступность), §8 (тесты), §9 этапы 3–4.

## Global Constraints

- Работа в ветке `frontend-landing`, рабочая копия `.worktrees/frontend-landing`; команды — из её корня.
- Новые npm-пакеты: `--save-exact`, версия опубликована ≥ 14 дней назад (`npm view <pkg> time --json`). Совместимость с React 18: `@react-three/fiber` **8.x**, `@react-three/drei` **9.x**, `three` в пределах peer-диапазона выбранного fiber, `motion` **12.x**.
- Дизайн-система плана 1 (`frontend/src/design/`): цвета только из токенов, `pencil` — только расхождения, элементы ≥ 26 px, фокус 2 px `blue`.
- Бюджеты (спецификация §7): точка входа ≤ 200 КБ gzip; чанк сцены ≤ 250 КБ gzip и грузится лениво; платформа (`/app…`) не тянет three.js.
- `prefers-reduced-motion: reduce`, ширина < 768 px или нет WebGL → вместо сцены SVG-кадры, без анимации появления текста.
- Факты на лендинге — только из репозитория (README, `src/ner/common/taxonomy.py`, конвейер), с указанием источника в файле контента; никаких придуманных чисел.
- Тексты лендинга — RU и KZ в словаре `frontend/src/landing/i18n.ts`, ключи совпадают; KZ отмечен на вычитку носителем (комментарий в файле).
- Анализ ТЭП (`src/`) и формат отчёта не меняются.

## Review Focus

1. **Пользователь уже вошёл и открывает `/`** — видит лендинг с кнопкой «Открыть платформу» вместо «Войти»; ссылки из писем (`/#access_token…`, `/#error…`) по-прежнему ведут на `/login`. → тест в Task 4.
2. **Двойная отправка заявки / заявка от бота** — повторное нажатие не шлёт вторую заявку; заполненное поле-ловушка отвечает «спасибо», ничего не сохраняя; шестая заявка с одной почты за сутки — понятный отказ. → тесты в Task 1 и Task 5.
3. **Демо без сети к API** — `/demo` и блок 04 работают только на статике: ни одного запроса к `/api/`, вердикт ставится локально и не теряется при смене замечания. → тест в Task 2.
4. **Телефон и «уменьшить движение»** — без WebGL-сцены и без анимаций; страница не прокручивается вбок. → тест в Task 6 и e2e в Task 8.
5. **Переключение RU ⇄ KZ** — все видимые тексты лендинга меняются, выбор помнится после перезагрузки; в KZ нет пропущенных ключей. → тест в Task 3.

---

## Структура файлов

```
api/main.py, api/_store.py               — POST /api/access-requests, хранение заявок, раздача /demo-data локально
supabase/migrations/20261012120000_access_requests.sql
scripts/export_demo.py                   — строит frontend/public/demo-data/{report.json, files/*.pdf}
tests/test_api_store.py, tests/test_export_demo.py
vercel.json                              — исключить demo-data/ из SPA-переписывания
frontend/
  public/demo-data/report.json, files/{PZ,AR,KR,SMETA}.pdf   — сгенерировано скриптом, в git
  src/
    platform/report/fileSource.ts        — контекст источника файлов (API или статика)
    platform/report/ReportPage.tsx       — ReportBody экспортируется, принимает onSave
    platform/report/RefPane.tsx          — берёт ссылку из контекста
    demo/DemoPage.tsx, demo/DemoReport.tsx, demo/loadDemo.ts
    landing/
      i18n.ts                            — RU/KZ словарь, useLang()
      content.ts                         — факты (метрики, типы проверок) с источниками
      LandingPage.tsx, Header.tsx, Footer.tsx, Reveal.tsx
      sections/{Hero,Problem,HowItWorks,LiveExample,Checks,Languages,Research,Security,AccessRequest}.tsx
      scene/sceneMath.ts, scene/chooseScene.ts, scene/useScrollProgress.ts, scene/Scene.tsx, scene/Fallback.tsx
    lib/api.ts                           — requestAccess()
    platform/shell/Sidebar.tsx           — вернуть «Демо» и «Методика»
    app/router.tsx                       — `/` → LandingPage (кроме ссылок из писем и ?check=), `/demo`
  e2e/landing.spec.ts
  scripts/check-budget.mjs               — бюджет чанка сцены
```

---

### Task 1: Заявки на доступ — бэкенд

**Files:**
- Modify: `api/_store.py`, `api/main.py`
- Create: `supabase/migrations/20261012120000_access_requests.sql`
- Test: `tests/test_api_store.py`

**Interfaces:**
- Produces: `POST /api/access-requests` body `{"email": str, "organization": str, "comment": str = "", "website": str = ""}` → `{"ok": true}`; `website` — ловушка для ботов (непустое → 200, не сохраняется); почта по `^[^@\s]+@[^@\s]+\.[^@\s]+$`, организация 1–200 символов, комментарий ≤ 1000 → иначе 422; > 5 заявок с одной почты за 24 ч → 429 `{"detail": "Слишком много заявок с этой почты, попробуйте завтра"}`. Вход не нужен.
- Store: `add_access_request(email: str, organization: str, comment: str) -> None`, `count_access_requests(email: str, since: datetime) -> int`.

- [ ] **Step 1: Падающие тесты**

Дописать в `tests/test_api_store.py`:

```python
def _ask(client, **over):
    body = {"email": "expert@bureau.kz", "organization": "ТОО «Бюро»", "comment": "", "website": ""} | over
    return client.post("/api/access-requests", json=body)


def test_access_request_is_stored(client, tmp_path):
    assert _ask(client, comment="хотим попробовать").json() == {"ok": True}
    rows = [json.loads(line) for line in (tmp_path / "_access_requests.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["email"] == "expert@bureau.kz" and rows[0]["organization"] == "ТОО «Бюро»"


def test_access_request_honeypot_is_silently_dropped(client, tmp_path):
    assert _ask(client, website="http://spam").json() == {"ok": True}
    assert not (tmp_path / "_access_requests.jsonl").exists()


def test_access_request_validation(client):
    assert _ask(client, email="not-an-email").status_code == 422
    assert _ask(client, organization="").status_code == 422
    assert _ask(client, comment="я" * 1001).status_code == 422


def test_access_request_limit_per_email(client):
    for _ in range(5):
        assert _ask(client).status_code == 200
    r = _ask(client)
    assert r.status_code == 429 and "завтра" in r.json()["detail"]
    assert _ask(client, email="other@bureau.kz").status_code == 200


def test_access_request_needs_no_login(authed):
    assert _ask(authed).status_code == 200


def test_access_requests_do_not_show_up_as_checks(client):
    _ask(client)
    assert client.get("/api/checks").json()["checks"] == []
```

(В начало файла — `import json`, если его нет.)

- [ ] **Step 2: Убедиться, что падают**

Run: `uv run pytest -q tests/test_api_store.py -k access_request`
Expected: FAIL (404 на `/api/access-requests`).

- [ ] **Step 3: Миграция**

`supabase/migrations/20261012120000_access_requests.sql`:

```sql
create table if not exists public.access_requests (
  id bigint generated always as identity primary key,
  email text not null check (length(email) between 3 and 320),
  organization text not null check (length(organization) between 1 and 200),
  comment text not null default '' check (length(comment) <= 1000),
  created_at timestamptz not null default now()
);
create index if not exists access_requests_email_created_idx on public.access_requests (email, created_at desc);
alter table public.access_requests enable row level security;
comment on table public.access_requests is 'Заявки «Запросить доступ» с лендинга. Доступ только с сервера.';
```

- [ ] **Step 4: Хранилища**

`api/_store.py`, `LocalStore` (заявки — строки JSON в `<root>/_access_requests.jsonl`; это файл, а не папка проверки, поэтому `list_checks` и `cleanup` его не видят — они перебирают только папки со `status.json`):

```python
    def _requests_path(self) -> Path:
        return self.root / "_access_requests.jsonl"

    def add_access_request(self, email: str, organization: str, comment: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        row = {"email": email, "organization": organization, "comment": comment, "created_at": datetime.now(UTC).isoformat()}
        with self._requests_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def count_access_requests(self, email: str, since: datetime) -> int:
        path = self._requests_path()
        if not path.is_file():
            return 0
        rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        return sum(1 for r in rows if r["email"] == email and datetime.fromisoformat(r["created_at"]) >= since)
```

`SupabaseStore`:

```python
    def add_access_request(self, email: str, organization: str, comment: str) -> None:
        self._rows("POST", table="access_requests", json={"email": email, "organization": organization, "comment": comment})

    def count_access_requests(self, email: str, since: datetime) -> int:
        rows = self._rows("GET", table="access_requests",
                          params={"email": f"eq.{email}", "created_at": f"gte.{since.isoformat()}", "select": "id"}).json()
        return len(rows)
```

- [ ] **Step 5: Эндпоинт**

`api/main.py` (перед SPA-маршрутом; описать в docstring модуля):

```python
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUESTS_PER_DAY = 5


class AccessRequest(BaseModel):
    email: str = Field(max_length=320)
    organization: str = Field(max_length=200)
    comment: str = Field(default="", max_length=1000)
    website: str = Field(default="", max_length=500)  # hidden field: people leave it empty, bots fill it


@app.post("/api/access-requests")
def access_request(body: AccessRequest) -> dict:
    if body.website:
        return {"ok": True}  # a bot: answer as usual, store nothing
    email, organization = body.email.strip().lower(), body.organization.strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "почта указана неверно")
    if not organization:
        raise HTTPException(422, "укажите организацию")
    store = _store()
    if store.count_access_requests(email, datetime.now(UTC) - timedelta(days=1)) >= REQUESTS_PER_DAY:
        raise HTTPException(429, "Слишком много заявок с этой почты, попробуйте завтра")
    store.add_access_request(email, organization, body.comment.strip())
    return {"ok": True}
```

Импорт: `from datetime import UTC, datetime, timedelta`.

- [ ] **Step 6: Тесты зелёные**

Run: `uv run ruff check api tests && uv run pytest -q tests/test_api_store.py tests/test_pipeline.py`
Expected: всё PASS.

- [ ] **Step 7: Commit**

```bash
git add api tests/test_api_store.py supabase
git commit -m "Заявки «Запросить доступ»: публичный эндпоинт, ловушка для ботов, 5 в сутки с почты"
```

---

### Task 2: Демо-отчёт без входа (`/demo`)

**Files:**
- Create: `scripts/export_demo.py`, `tests/test_export_demo.py`, `frontend/public/demo-data/report.json`, `frontend/public/demo-data/files/{PZ,AR,KR,SMETA}.pdf`, `frontend/src/platform/report/fileSource.ts`, `frontend/src/demo/loadDemo.ts`, `frontend/src/demo/DemoReport.tsx`, `frontend/src/demo/DemoPage.tsx`, `frontend/src/demo/demo.test.tsx`
- Modify: `frontend/src/platform/report/ReportPage.tsx`, `frontend/src/platform/report/RefPane.tsx`, `frontend/src/app/router.tsx`, `api/main.py`, `vercel.json`, `frontend/src/lib/i18n.ts`

**Interfaces:**
- Produces:
  - `scripts/export_demo.py [--out DIR]` → `DIR/report.json` (отчёт без `path`, с `"title"`) и `DIR/files/*.pdf`; по умолчанию `frontend/public/demo-data`.
  - `fileSource.ts`: `export type FileSource = (checkId: string, name: string) => Promise<string>`; `FileSourceContext` (по умолчанию — `fileLink` из `lib/api`); `staticFileSource(base: string): FileSource` → `` `${base}/files/${encodeURIComponent(name)}` ``.
  - `ReportPage.tsx`: `export function ReportBody(props: { checkId: string; report: Report; title: string; initial: Reviews; onSave?: (finding: number, r: Review) => Promise<void> })` — по умолчанию сохранение через API.
  - `loadDemo(): Promise<{ report: Report; title: string }>` — `fetch("/demo-data/report.json")`.
  - `<DemoReport height?: string />` — `ReportBody` на демо-данных со `staticFileSource("/demo-data")` и `onSave` без сети; `<DemoPage />` — `/demo` с шапкой «Это пример…» и кнопками «Войти» / «Запросить доступ».

- [ ] **Step 1: Падающие тесты**

`tests/test_export_demo.py`:

```python
import json
import subprocess
import sys


def test_export_demo_writes_report_and_pdfs(tmp_path):
    subprocess.run([sys.executable, "scripts/export_demo.py", "--out", str(tmp_path)], check=True)
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["MISMATCH"] == 3 and report["title"]
    assert all("path" not in d for d in report["documents"])
    assert sorted(p.name for p in (tmp_path / "files").iterdir()) == ["AR.pdf", "KR.pdf", "PZ.pdf", "SMETA.pdf"]
```

`frontend/src/demo/demo.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { staticFileSource } from "../platform/report/fileSource";

describe("demo", () => {
  it("files of the demo come from static data, not the API (Review Focus 3)", async () => {
    expect(await staticFileSource("/demo-data")("x", "ПЗ.pdf")).toBe("/demo-data/files/%D0%9F%D0%97.pdf");
  });

  it("the demo report renders from static data and saves verdicts locally", async () => {
    const report = (await import("../../public/demo-data/report.json")).default;
    const calls: string[] = [];
    const origFetch = globalThis.fetch;
    globalThis.fetch = (async (u: RequestInfo | URL) => { calls.push(String(u)); return new Response(JSON.stringify(report)); }) as typeof fetch;
    const { default: DemoReport } = await import("./DemoReport");
    const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
    const { MemoryRouter } = await import("react-router");
    // ReportBody reads ?f= (⌘K jump to a finding), so it needs a router like on /demo
    render(<MemoryRouter><QueryClientProvider client={new QueryClient()}><DemoReport /></QueryClientProvider></MemoryRouter>);
    expect(await screen.findByRole("heading", { level: 2, name: "Общая площадь, м²" })).toBeInTheDocument();
    screen.getByRole("button", { name: /Подтверждаю/ }).click();
    expect(await screen.findByText("1/4")).toBeInTheDocument();
    expect(calls.filter(u => u.includes("/api/"))).toEqual([]);
    globalThis.fetch = origFetch;
  });
});
```

(Второй тест рендерит `RefPane` → pdf.js; в jsdom нет canvas/worker — pdf.js падает асинхронно внутри `RefPane`, который ловит ошибку и пишет её в заметку (`setNote`), отчёт при этом рисуется. Если импорт `pdfjs-dist` в jsdom падает синхронно, замокать его в тесте: `vi.mock("pdfjs-dist", () => ({ GlobalWorkerOptions: {}, getDocument: () => ({ promise: new Promise(() => {}) }) }))` и `vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({ default: "" }))`.)

- [ ] **Step 2: Убедиться, что падают**

Run: `uv run pytest -q tests/test_export_demo.py; npm --prefix frontend test -- src/demo`
Expected: FAIL (нет скрипта; нет модулей).

- [ ] **Step 3: Скрипт экспорта и данные**

`scripts/export_demo.py`:

```python
"""Static demo report for the landing page and /demo (no login, no API): report.json + the PDFs it cites.

Run after changes to the pipeline:  uv run python scripts/export_demo.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.main import default_title  # noqa: E402
from src.pipeline import analyze_package  # noqa: E402

SAMPLE = ROOT / "data" / "synthetic" / "samples" / "ru" / "ru_00001" / "text"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "frontend" / "public" / "demo-data")
    out = ap.parse_args().out
    files = sorted(SAMPLE.glob("*.pdf"))
    report = analyze_package(files)
    for doc in report["documents"]:
        doc.pop("path", None)
    report["title"] = default_title(report, [f.name for f in files])
    (out / "files").mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy(f, out / "files" / f.name)
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"demo: {out} ({len(files)} files, {len(report['findings'])} findings)")


if __name__ == "__main__":
    main()
```

Выполнить: `uv run python scripts/export_demo.py` — создаёт `frontend/public/demo-data/`.

- [ ] **Step 4: Источник файлов и сохранение — параметры отчёта**

`frontend/src/platform/report/fileSource.ts`:

```ts
import { createContext } from "react";
import { fileLink } from "../../lib/api";

/** Where the report's PDFs come from: a signed link from the API, or static files of the demo. */
export type FileSource = (checkId: string, name: string) => Promise<string>;

export const staticFileSource = (base: string): FileSource =>
  async (_checkId, name) => `${base}/files/${encodeURIComponent(name)}`;

export const FileSourceContext = createContext<FileSource>(fileLink);
```

`RefPane.tsx`: убрать `import { fileLink } from "../../lib/api";`, добавить `import { useContext } from "react";` (в существующий импорт) и `import { FileSourceContext } from "./fileSource";`; в теле компонента `const source = useContext(FileSourceContext);`; в загрузке `fileLink(checkId, doc.file)` → `source(checkId, doc.file)`; ключ кэша `` `${checkId}/${doc.file}` `` оставить.

`ReportPage.tsx`: `function ReportBody(` → `export function ReportBody(`; в пропсы добавить `onSave?: (finding: number, r: Review) => Promise<void>`; очередь: `createReviewQueue((n, r) => (onSave ?? ((f, rv) => saveReview(checkId, f, rv)))(n, r))`.

- [ ] **Step 5: Демо-компоненты и маршрут**

`frontend/src/demo/loadDemo.ts`:

```ts
import type { Report } from "../lib/types";

export async function loadDemo(): Promise<{ report: Report; title: string }> {
  const r = await fetch("/demo-data/report.json");
  if (!r.ok) throw new Error(`демо не загрузилось: ${r.status}`);
  const report = (await r.json()) as Report & { title: string };
  return { report, title: report.title };
}
```

`frontend/src/demo/DemoReport.tsx`:

```tsx
import { useEffect, useState } from "react";
import EmptyState from "../design/EmptyState";
import { t } from "../lib/i18n";
import type { Report } from "../lib/types";
import { staticFileSource, FileSourceContext } from "../platform/report/fileSource";
import { ReportBody } from "../platform/report/ReportPage";
import { loadDemo } from "./loadDemo";

const DEMO = "0".repeat(32); // the demo has no check id; the report only uses it as a cache key
const source = staticFileSource("/demo-data");

/** The real report on the bundled sample: no login, no API; verdicts stay in the page. */
export default function DemoReport({ height = "100%" }: { height?: string }) {
  const [data, setData] = useState<{ report: Report; title: string } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { loadDemo().then(setData, e => setError((e as Error).message)); }, []);
  if (error) return <EmptyState title={error} />;
  if (!data) return <p className="p-6 text-ink-2">{t("common.loading")}</p>;
  return (
    <FileSourceContext.Provider value={source}>
      <div style={{ height }} className="flex flex-col min-h-0 bg-tracing">
        <ReportBody checkId={DEMO} report={data.report} title={data.title} initial={{}} onSave={async () => {}} />
      </div>
    </FileSourceContext.Provider>
  );
}
```

`frontend/src/demo/DemoPage.tsx`:

```tsx
import { Link } from "react-router";
import Button from "../design/Button";
import { t } from "../lib/i18n";
import DemoReport from "./DemoReport";

export default function DemoPage() {
  return (
    <div className="flex flex-col h-full">
      <header className="flex flex-wrap items-center gap-3 px-4 py-2 bg-sheet border-b border-line">
        <Link to="/" className="font-cond font-semibold">{t("app.name")}</Link>
        <span className="text-sm text-ink-2 flex-1 min-w-48">{t("demo.banner")}</span>
        <Link to="/#access"><Button size="sm">{t("demo.request")}</Button></Link>
        <Link to="/login"><Button size="sm" variant="primary">{t("demo.login")}</Button></Link>
      </header>
      <div className="flex-1 min-h-0 overflow-auto"><DemoReport /></div>
    </div>
  );
}
```

`lib/i18n.ts` — ключи: `"demo.banner": "Это пример отчёта на демонстрационном пакете: вердикты не сохраняются."`, `"demo.request": "Запросить доступ"`, `"demo.login": "Войти"`.

`app/router.tsx`: `const DemoPage = lazy(() => import("../demo/DemoPage"));` и маршрут `{ path: "/demo", element: page(<DemoPage />), errorElement: <RouteErrorElement /> }` (до `*`).

Раздача статики: `vercel.json` — в правиле SPA `demo/` → `demo-data/`: `"/((?!api/|assets/|demo-data/).*)"`. `api/main.py` — рядом с `/assets`:

```python
if (FRONTEND / "demo-data").is_dir():
    app.mount("/demo-data", StaticFiles(directory=FRONTEND / "demo-data"), name="demo-data")
```

и в `spa()` — `if path.startswith(("api/", "assets/", "demo-data/")):`.

- [ ] **Step 6: Тесты зелёные**

Run: `uv run pytest -q tests/test_export_demo.py tests/test_api_store.py && npm --prefix frontend test && npx --prefix frontend tsc -b frontend`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/export_demo.py tests/test_export_demo.py frontend api vercel.json
git commit -m "Демо без входа: статический отчёт по примеру, /demo на том же компоненте отчёта"
```

---

### Task 3: Языки лендинга (RU/KZ)

**Files:**
- Create: `frontend/src/landing/i18n.ts`, `frontend/src/landing/i18n.test.ts`

**Interfaces:**
- Produces: `type Lang = "ru" | "kz"`; `RU` и `KZ` — словари с одинаковыми ключами (`type LKey = keyof typeof RU`, `KZ: Record<LKey, string>`); `tlFor(lang: Lang): (key: LKey, vars?) => string`; `useLang(): { lang: Lang; setLang(l: Lang): void; tl(key: LKey, vars?): string }` — выбор в `localStorage["tep.lang"]` (try/catch), по умолчанию `ru`; меняет `document.documentElement.lang` на `ru` / `kk`; `LangContext = createContext<ReturnType<typeof useLang>>({ lang: "ru", setLang: () => {}, tl: tlFor("ru") })` — `LandingPage` кладёт в него `useLang()`, блоки читают `useContext(LangContext)` (по умолчанию RU — блок рисуется и отдельно, например в тесте формы).
- Ключи (используются в Task 4–6): `nav.how`, `nav.research`, `nav.login`, `nav.open`, `hero.title`, `hero.lead`, `hero.demo`, `hero.login`, `problem.title`, `problem.sections`, `problem.fields`, `problem.types`, `problem.lead`, `how.title`, `how.step1.title`, `how.step1.text`, `how.step2.title`, `how.step2.text`, `how.step3.title`, `how.step3.text`, `example.title`, `example.lead`, `example.open`, `checks.title`, `checks.lead`, `checks.scanNote`, `langs.title`, `langs.lead`, `langs.ru`, `langs.kz`, `research.title`, `research.lead`, `research.extraction`, `research.detectors`, `research.real`, `research.limits`, `research.source`, `security.title`, `security.invite`, `security.own`, `security.retention`, `security.noLlm`, `access.title`, `access.lead`, `access.email`, `access.org`, `access.comment`, `access.send`, `access.sending`, `access.done`, `footer.thesis`, `footer.github`, `scene.alt`, `type.<DiscrepancyType>` для 11 типов из Task 4.

- [ ] **Step 1: Падающий тест**

`frontend/src/landing/i18n.test.ts`:

```ts
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { KZ, RU, useLang } from "./i18n";

describe("landing languages (Review Focus 5)", () => {
  beforeEach(() => localStorage.clear());

  it("Kazakh has every key of Russian and no empty text", () => {
    expect(Object.keys(KZ).sort()).toEqual(Object.keys(RU).sort());
    expect(Object.entries(KZ).filter(([, v]) => !v.trim())).toEqual([]);
  });

  it("the choice switches texts, is remembered and sets <html lang>", () => {
    const { result } = renderHook(() => useLang());
    expect(result.current.tl("hero.demo")).toBe(RU["hero.demo"]);
    act(() => result.current.setLang("kz"));
    expect(result.current.tl("hero.demo")).toBe(KZ["hero.demo"]);
    expect(localStorage.getItem("tep.lang")).toBe("kz");
    expect(document.documentElement.lang).toBe("kk");
    expect(renderHook(() => useLang()).result.current.lang).toBe("kz");
  });
});
```

- [ ] **Step 2: Убедиться, что падает**

Run: `npm --prefix frontend test -- src/landing/i18n`
Expected: FAIL — модуль не найден.

- [ ] **Step 3: Словари и хук**

`frontend/src/landing/i18n.ts` — заголовок файла:

```ts
// Тексты лендинга. KZ написан сразу; перед публикацией его вычитывает носитель языка.
import { createContext, useCallback, useEffect, useState } from "react";

export type Lang = "ru" | "kz";
```

затем `export const RU = { … } as const;` со всеми ключами из Interfaces (тексты — по блокам спецификации §4; числа в текстах не пишутся — они подставляются из `content.ts` через переменные `{n}`), `export type LKey = keyof typeof RU;`, `export const KZ: Record<LKey, string> = { … };` (те же ключи по-казахски), и хук:

```ts
const KEY = "tep.lang";
const read = (): Lang => { try { return localStorage.getItem(KEY) === "kz" ? "kz" : "ru"; } catch { return "ru"; } };

export function useLang() {
  const [lang, setLangState] = useState<Lang>(read);
  useEffect(() => { document.documentElement.lang = lang === "kz" ? "kk" : "ru"; }, [lang]);
  const setLang = useCallback((l: Lang) => {
    try { localStorage.setItem(KEY, l); } catch { /* blocked storage */ }
    setLangState(l);
  }, []);
  const tl = useCallback(tlFor(lang), [lang]);
  return { lang, setLang, tl };
}

export const tlFor = (lang: Lang) => (key: LKey, vars: Record<string, string | number> = {}) =>
  (lang === "kz" ? KZ : RU)[key].replace(/\{(\w+)\}/g, (_, v) => String(vars[v] ?? ""));

export const LangContext = createContext<ReturnType<typeof useLang>>({ lang: "ru", setLang: () => {}, tl: tlFor("ru") });
```

Обязательные значения RU (остальные — по смыслу блока, коротко, без чисел):
`"hero.title": "Сверка технико-экономических показателей проекта"`, `"hero.lead": "ПЗ, АР, КР и смета на русском и казахском: расхождения находятся за минуты и обводятся прямо на странице документа."`, `"hero.demo": "Попробовать демо"`, `"hero.login": "Войти"`, `"nav.open": "Открыть платформу"`, `"security.retention": "Проверки и файлы удаляются через {n} дней"`, `"security.noLlm": "Документы не отправляются в сторонние ИИ-сервисы"`, `"research.source": "Источник: README репозитория, разделы оценки"`.

- [ ] **Step 4: Тест зелёный, commit**

Run: `npm --prefix frontend test -- src/landing/i18n` → PASS.

```bash
git add frontend/src/landing/i18n.ts frontend/src/landing/i18n.test.ts
git commit -m "Лендинг: словари RU/KZ и выбор языка"
```

---

### Task 4: Лендинг — страница, блоки, факты

**Files:**
- Create: `frontend/src/landing/content.ts`, `frontend/src/landing/LandingPage.tsx`, `frontend/src/landing/Header.tsx`, `frontend/src/landing/Footer.tsx`, `frontend/src/landing/Reveal.tsx`, `frontend/src/landing/sections/{Hero,Problem,HowItWorks,LiveExample,Checks,Languages,Research,Security}.tsx`, `frontend/src/landing/landing.test.tsx`
- Modify: `frontend/src/app/router.tsx`, `frontend/package.json` (motion)

**Interfaces:**
- Consumes: `useLang` (Task 3), `useSession` (план 1), `DemoReport` (Task 2, лениво), `Scene`/`Fallback` (Task 6 — до неё в Hero стоит `Fallback`).
- Produces:
  - `content.ts`: `CHECK_TYPES: readonly DiscrepancyKey[]` — 11 типов, которые сейчас выдаёт конвейер (`AREA_PZ_VS_AR_EXPLICATION`, `MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE`, `COST_OBJECT_ESTIMATE_VS_SUMMARY`, `MISSING_MANDATORY_TEP`, `TEP_CROSS_SECTION_MISMATCH`, `TABLE_TOTAL_MISMATCH`, `VALUE_CROSS_SECTION_MISMATCH`, `PARAMETER_CONTRADICTION`, `TEP_CALCULATION_METHOD`, `GEOMETRY_INCONSISTENCY`, `COPY_PASTE_LABEL`); `SCAN_LIMITED: readonly DiscrepancyKey[]` — те, что на сканах ограничены (`TABLE_TOTAL_MISMATCH`, `MISSING_MANDATORY_TEP`); `FACTS` — `{ sections: 4, tepFields: 8, checkTypes: 11, retentionDays: 7 }`; `METRICS` — `{ extraction: { ru: "0,97", kz: "0,81", set: "v3-test" }, detectors: { ru: "1,00", kz: "1,00", set: "v4-test" }, real: { tep: "8 из 10", findings: "4 из 10", falsePositives: 0 } }`. Каждое значение с комментарием-источником (`README.md`, раздел и таблица; `src/ner/data/tep_lexicon.json` → `fields`; `src/crossvalidation`).
  - `LandingPage` — блоки с `id`: `how`, `example`, `checks`, `languages`, `research`, `security`, `access`; `Root` в роутере рисует его на `/` (ссылки из писем → `/login`, `?check=` → отчёт — как в плане 1).
  - `Reveal` — обёртка появления (motion `whileInView`, `opacity`/`y`), при `useReducedMotion()` — без анимации.

- [ ] **Step 1: Падающие тесты**

`frontend/src/landing/landing.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SessionContext, type Session } from "../app/providers";
import { CHECK_TYPES, FACTS, METRICS } from "./content";
import { KZ, RU } from "./i18n";
import LandingPage from "./LandingPage";

vi.mock("../demo/DemoReport", () => ({ default: () => <div>demo report</div> }));

const session = (over: Partial<Session> = {}): Session => ({
  ready: true, enabled: true, email: null, ocr: true, signOut: vi.fn(), refresh: vi.fn(), ...over,
});
const show = (s = session()) =>
  render(<SessionContext.Provider value={s}><MemoryRouter><LandingPage /></MemoryRouter></SessionContext.Provider>);

describe("landing", () => {
  beforeEach(() => localStorage.clear());

  it("has the nine blocks in order", () => {
    show();
    const titles = screen.getAllByRole("heading", { level: 2 }).map(h => h.textContent);
    expect(titles).toEqual([RU["problem.title"], RU["how.title"], RU["example.title"], RU["checks.title"],
      RU["langs.title"], RU["research.title"], RU["security.title"], RU["access.title"]]);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(RU["hero.title"]);
  });

  it("facts and metrics come from content.ts", () => {
    show();
    const research = within(document.getElementById("research")!);
    expect(research.getByText(METRICS.extraction.ru)).toBeInTheDocument();
    expect(research.getByText(METRICS.real.tep)).toBeInTheDocument();
    expect(within(document.getElementById("checks")!).getAllByRole("listitem")).toHaveLength(CHECK_TYPES.length);
    expect(screen.getByText(RU["security.retention"].replace("{n}", String(FACTS.retentionDays)))).toBeInTheDocument();
  });

  it("signed out: «Войти» (Review Focus 1)", () => {
    show();
    expect(screen.getAllByRole("link", { name: RU["nav.login"] })[0]).toHaveAttribute("href", "/login");
  });

  it("signed in: «Открыть платформу» instead of «Войти» (Review Focus 1)", () => {
    show(session({ email: "a@b.kz" }));
    expect(screen.getAllByRole("link", { name: RU["nav.open"] })[0]).toHaveAttribute("href", "/app");
    expect(screen.queryByRole("link", { name: RU["nav.login"] })).toBeNull();
  });

  it("the language switch turns the whole page Kazakh", () => {
    show();
    screen.getByRole("button", { name: "KZ" }).click();
    return screen.findByRole("heading", { level: 1, name: KZ["hero.title"] });
  });
});
```

Дописать в `frontend/src/app/router.test.tsx` (там уже есть `at()` и `session()`); `vi.mock` — на верхнем уровне файла, рядом с импортами (Vitest всё равно поднимает его туда):

```tsx
vi.mock("../landing/LandingPage", () => ({ default: () => <h1>landing</h1> }));

it("/ shows the landing, links from emails still go to /login (Review Focus 1)", async () => {
  at("/", session());
  expect(await screen.findByRole("heading", { name: "landing" })).toBeInTheDocument();
  const router = at("/#access_token=x&type=recovery", session());
  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
});
```

- [ ] **Step 2: Убедиться, что падают**

Run: `npm --prefix frontend test -- src/landing src/app`
Expected: FAIL — модули не найдены; `/` уводит на `/app`.

- [ ] **Step 3: Motion и факты**

```bash
npm --prefix frontend install --save-exact motion@<12.x, ≥ 14 дней>
```

`frontend/src/landing/content.ts` — как в Interfaces, тип `DiscrepancyKey` — строковый литерал-юнион 11 значений; комментарии над `METRICS`:

```ts
// README.md, «Проверка на скрытых формулировках», таблица «Ступени»: + эмбеддинги, F1 по слотам, v3-test
// README.md, «итог — один прогон на seeds 9000–9099», строка «все типы», столбцы S2 RU / S2 KZ, v4-test
// README.md, «Реальная ОПЗ (единственный документ, dev)»: ТЭП, размеченные находки, ложных — 0
```

`Reveal.tsx`:

```tsx
import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

/** Fades a block in when it scrolls into view; still when the system asks for less motion. */
export default function Reveal({ children, className }: { children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div className={className} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-10% 0px" }} transition={{ duration: 0.25, ease: "easeOut" }}>
      {children}
    </motion.div>
  );
}
```

- [ ] **Step 4: Страница и блоки**

`LandingPage.tsx` — `const lang = useLang();` и `<LangContext.Provider value={lang}>` вокруг всей страницы; блоки берут `const { tl } = useContext(LangContext)`. Раскладка:

```tsx
<div className="min-h-full bg-paper">
  <Header />                                    {/* лого, якоря #how #research, RU|KZ (кнопки "RU"/"KZ", aria-pressed), Войти/Открыть платформу */}
  <main>
    <Hero />                                    {/* h1, lead, «Попробовать демо» → /demo, «Войти»; справа сцена (Task 6) */}
    <Problem /> <HowItWorks /> <LiveExample /> <Checks /> <Languages /> <Research /> <Security /> <AccessRequest />
  </main>
  <Footer />
</div>
```

Каждый блок — `<section id=… aria-labelledby=…><Reveal><h2 id=…>…</h2>…</Reveal></section>`, ширина `max-w-6xl mx-auto px-4 md:px-6 py-16 md:py-24`, сетка кальки `bg-tracing` у чётных блоков. Содержание по спецификации §4:
- **Problem** — три счётчика `num text-4xl`: `FACTS.sections` (`problem.sections`), `FACTS.tepFields` (`problem.fields`), `FACTS.checkTypes` (`problem.types`).
- **HowItWorks** (`id="how"`) — три шага `<ol>`, номер `num text-blue`.
- **LiveExample** (`id="example"`) — `lazy(() => import("../demo/DemoReport"))` в рамке `h-[640px] border border-line`, под ней ссылка `example.open` → `/demo`.
- **Checks** (`id="checks"`) — `<ul>` из `CHECK_TYPES`: `tl(\`type.${t}\`)`, у `SCAN_LIMITED` — `Badge kind="scan"`; под списком `checks.scanNote`.
- **Languages** — две строки цитаты (`langs.ru`, `langs.kz`) с подсвеченным числом `1 247,79` (`text-pencil num`).
- **Research** (`id="research"`) — карточки `METRICS` (`num text-3xl` + подпись с набором), абзац `research.limits`, подпись `research.source`.
- **Security** — четыре пункта с иконками-галочками `text-green`, `security.retention` с `{n}` = `FACTS.retentionDays`.
- **AccessRequest** (`id="access"`) — Task 5; до неё — заголовок и `access.lead`.
- **Footer** — `footer.thesis`, ссылка на GitHub `https://github.com/00monaliza/doc-tep-validator`.

`Header` — `sticky top-0 z-20 bg-sheet/90 backdrop-blur border-b border-line`; на `< md` якоря скрыты, остаются RU/KZ и «Войти».

`app/router.tsx`:

```tsx
const LandingPage = lazy(() => import("../landing/LandingPage"));
…
function Root() {
  const loc = useLocation();
  if (AUTH_FRAGMENT.test(loc.hash)) return <Navigate to={{ pathname: "/login", hash: loc.hash }} replace />;
  const legacy = legacyRedirect(loc.search);
  if (legacy) return <Navigate to={legacy} replace />;
  return page(<LandingPage />);
}
```

- [ ] **Step 5: Тесты зелёные**

Run: `npm --prefix frontend test && npx --prefix frontend tsc -b frontend`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "Лендинг: девять блоков, факты из репозитория, RU/KZ, появление при прокрутке"
```

---

### Task 5: Форма «Запросить доступ»

**Files:**
- Create: `frontend/src/landing/sections/AccessRequest.tsx`, `frontend/src/landing/access.test.tsx`
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Consumes: `POST /api/access-requests` (Task 1); `tl` (Task 3).
- Produces: `requestAccess(body: { email: string; organization: string; comment: string; website: string }): Promise<void>` — ошибки сервера → `Error(detail)`.

- [ ] **Step 1: Падающий тест**

`frontend/src/landing/access.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RU } from "./i18n";
import AccessRequest from "./sections/AccessRequest";

const fill = async () => {
  await userEvent.type(screen.getByLabelText(RU["access.email"]), "expert@bureau.kz");
  await userEvent.type(screen.getByLabelText(RU["access.org"]), "ТОО «Бюро»");
};

describe("access request (Review Focus 2)", () => {
  it("sends once even on a double click and thanks the user", async () => {
    let resolve!: (r: Response) => void;
    const fetchMock = vi.fn(() => new Promise<Response>(r => { resolve = r; }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AccessRequest />);
    await fill();
    const send = screen.getByRole("button", { name: RU["access.send"] });
    await userEvent.dblClick(send);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolve(new Response(JSON.stringify({ ok: true })));
    expect(await screen.findByText(RU["access.done"])).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("shows the server's refusal", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Слишком много заявок с этой почты, попробуйте завтра" }), { status: 429 })));
    render(<AccessRequest />);
    await fill();
    await userEvent.click(screen.getByRole("button", { name: RU["access.send"] }));
    expect(await screen.findByRole("alert")).toHaveTextContent("попробуйте завтра");
    vi.unstubAllGlobals();
  });

  it("the bot trap is invisible and out of the tab order", () => {
    render(<AccessRequest />);
    const trap = document.querySelector('input[name="website"]')!;
    expect(trap).toHaveAttribute("tabindex", "-1");
    expect(trap.closest("[aria-hidden='true']")).not.toBeNull();
  });
});
```

- [ ] **Step 2: Убедиться, что падает** — `npm --prefix frontend test -- src/landing/access` → FAIL.

- [ ] **Step 3: Реализация**

`lib/api.ts`:

```ts
export async function requestAccess(body: { email: string; organization: string; comment: string; website: string }): Promise<void> {
  await json(fetch("/api/access-requests", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }), "Заявка не отправлена.");
}
```

`landing/sections/AccessRequest.tsx` — форма (`id="access"`), поля с `<label>` (`access.email` type=email required, `access.org` required, `access.comment` textarea maxLength 1000), поле-ловушка `<div aria-hidden="true" className="absolute -left-[9999px]"><input name="website" tabIndex={-1} autoComplete="off" …/></div>`, состояние `idle | sending | done | error`; кнопка `disabled` при `sending` и `done`, обработчик сразу выходит, если уже `sending` (защита от двойного нажатия до перерисовки — через `useRef` флаг); `done` → `access.done` в `role="status"`; ошибка → `role="alert"`. `tl` — из `useContext(LangContext)`.

- [ ] **Step 4: Зелёные, commit**

Run: `npm --prefix frontend test` → PASS.

```bash
git add frontend
git commit -m "Лендинг: форма «Запросить доступ» с защитой от двойной отправки и ботов"
```

---

### Task 6: 3D-сцена «Расслоение» и запасные кадры

**Files:**
- Create: `frontend/src/landing/scene/sceneMath.ts`, `frontend/src/landing/scene/chooseScene.ts`, `frontend/src/landing/scene/useScrollProgress.ts`, `frontend/src/landing/scene/Scene.tsx`, `frontend/src/landing/scene/Fallback.tsx`, `frontend/src/landing/scene/scene.test.ts`
- Modify: `frontend/src/landing/sections/Hero.tsx`, `frontend/src/landing/LandingPage.tsx`, `frontend/package.json`, `frontend/scripts/check-budget.mjs`

**Interfaces:**
- Produces:
  - `sceneMath.ts` (прогресс `p` ∈ [0, 1] — от начала Hero до конца блока `how`):
    - `LAYERS = ["PZ", "AR", "KR", "SMETA"] as const`;
    - `layerY(p: number, i: number): number` — высота этажа `i`: при `p ≤ 0.15` все вместе (`i * 0.6`), к `p = 0.5` раздвинуты до `i * 1.6`, дальше не меняется; монотонно по `p`;
    - `numbersOpacity(p: number): number` — 0 до `0.35`, линейно до 1 к `0.6`;
    - `ringProgress(p: number): number` — 0 до `0.7`, линейно до 1 к `0.9` (доля прорисовки красной обводки);
    - `clamp01(x: number): number`.
  - `chooseScene(env: { reducedMotion: boolean; width: number; webgl: boolean }): "scene" | "fallback"` — `scene` только при `!reducedMotion && width >= 768 && webgl`.
  - `useScrollProgress(startId: string, endId: string): number` — доля прокрутки между верхом `#startId` и низом `#endId`, обновление по `scroll`/`resize` через `requestAnimationFrame`.
  - `<Scene progress: number />` — `Canvas` (react-three-fiber), 4 этажа-«плиты» из `LineSegments` (`EdgesGeometry` от `BoxGeometry(4, 0.5, 3)`), цвет `--blue` из `getComputedStyle`, лёгкий поворот за указателем (`useFrame`, ±8°), на этажах ПЗ и АР — `drei/Html` с числами `1 247,79` / `1 382` (`opacity = numbersOpacity`), между ними — красная обводка (эллипс `Line` из drei, `dashOffset` по `ringProgress`), подпись «≠ 9,7 %»; `aria-hidden`, рядом `sr-only` текст `scene.alt`.
  - `<Fallback progress?: number />` — SVG того же рисунка (3 кадра из брейншторма: целое здание / разошедшиеся этажи / обводка), выбирается по `progress` (без анимации).

- [ ] **Step 1: Пакеты**

```bash
npm --prefix frontend install --save-exact three@<в peer @react-three/fiber 8> @react-three/fiber@<8.x> @react-three/drei@<9.x>
npm --prefix frontend install --save-exact -D @types/three@<в тон three>
```

- [ ] **Step 2: Падающий тест**

`frontend/src/landing/scene/scene.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { chooseScene } from "./chooseScene";
import { clamp01, LAYERS, layerY, numbersOpacity, ringProgress } from "./sceneMath";

describe("scene layout (pure)", () => {
  it("floors start together, spread by the middle and stay ordered", () => {
    expect(LAYERS.map((_, i) => layerY(0, i))).toEqual([0, 0.6, 1.2, 1.8]);
    expect(LAYERS.map((_, i) => layerY(0.5, i))).toEqual([0, 1.6, 3.2, 4.8]);
    expect(layerY(1, 3)).toBe(layerY(0.5, 3));
    for (let p = 0; p <= 1; p += 0.05) expect(layerY(p + 0.05, 2)).toBeGreaterThanOrEqual(layerY(p, 2));
  });

  it("numbers appear after the floors part, the ring last", () => {
    expect(numbersOpacity(0.3)).toBe(0);
    expect(numbersOpacity(0.6)).toBe(1);
    expect(ringProgress(0.69)).toBe(0);
    expect(ringProgress(0.8)).toBeCloseTo(0.5);
    expect(ringProgress(1)).toBe(1);
    expect(clamp01(-1)).toBe(0);
  });

  it("the live scene only where it can run (Review Focus 4)", () => {
    expect(chooseScene({ reducedMotion: false, width: 1366, webgl: true })).toBe("scene");
    expect(chooseScene({ reducedMotion: true, width: 1366, webgl: true })).toBe("fallback");
    expect(chooseScene({ reducedMotion: false, width: 375, webgl: true })).toBe("fallback");
    expect(chooseScene({ reducedMotion: false, width: 1366, webgl: false })).toBe("fallback");
  });
});
```

- [ ] **Step 3: Убедиться, что падает** — `npm --prefix frontend test -- src/landing/scene` → FAIL.

- [ ] **Step 4: Чистые функции**

`sceneMath.ts`:

```ts
export const LAYERS = ["PZ", "AR", "KR", "SMETA"] as const;
export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const ramp = (p: number, from: number, to: number) => clamp01((p - from) / (to - from));

/** Height of floor i: together at first, spread out by the middle of the scroll. */
export const layerY = (p: number, i: number) => +(i * (0.6 + 1.0 * ramp(p, 0.15, 0.5))).toFixed(4);
export const numbersOpacity = (p: number) => ramp(p, 0.35, 0.6);
export const ringProgress = (p: number) => ramp(p, 0.7, 0.9);
```

`chooseScene.ts`:

```ts
export function chooseScene(env: { reducedMotion: boolean; width: number; webgl: boolean }): "scene" | "fallback" {
  return !env.reducedMotion && env.width >= 768 && env.webgl ? "scene" : "fallback";
}

export function hasWebGL(): boolean {
  try { return !!document.createElement("canvas").getContext("webgl2"); } catch { return false; }
}
```

- [ ] **Step 5: Сцена, кадры, подключение**

`Scene.tsx` и `Fallback.tsx` — по Interfaces. `Hero.tsx`:

```tsx
const Scene = lazy(() => import("../scene/Scene")); // own chunk: three.js only on the landing
…
const progress = useScrollProgress("hero", "how");
const [mode] = useState(() => chooseScene({
  reducedMotion: matchMedia("(prefers-reduced-motion: reduce)").matches, width: innerWidth, webgl: hasWebGL(),
}));
…
<div className="relative h-[420px] md:h-[560px]">
  {mode === "scene"
    ? <Suspense fallback={<Fallback progress={0} />}><Scene progress={progress} /></Suspense>
    : <Fallback progress={progress} />}
</div>
```

Сцена «закреплена» до конца блока `how`: обёртка Hero + Problem + HowItWorks — `grid md:grid-cols-[1fr_minmax(0,46%)]`, правая колонка `md:sticky md:top-16 md:h-[calc(100vh-4rem)]`.

`frontend/scripts/check-budget.mjs` — после проверки точки входа:

```js
// the scene chunk (landing only) may contain three.js but has its own budget (spec §7)
for (const f of files.filter(f => /^Scene-/.test(f))) {
  if (kb(f) > 250) { console.error(`${f}: ${kb(f).toFixed(0)} KB gzip > 250`); failed = true; }
}
```

и условие проверки платформы: `!/^Scene-/.test(f)` вместо `!/scene/i.test(f)`.

- [ ] **Step 6: Зелёные, бюджет, commit**

Run: `npm --prefix frontend test && npm --prefix frontend run budget`
Expected: PASS; точка входа ≤ 200 КБ, `Scene-*.js` ≤ 250 КБ, `WebGLRenderer` только в `Scene-*`.

```bash
git add frontend
git commit -m "Лендинг: 3D-сцена «Расслоение» по прокрутке и запасные SVG-кадры"
```

---

### Task 7: Меню платформы, e2e, бюджет, ручная проверка

**Files:**
- Modify: `frontend/src/platform/shell/Sidebar.tsx` (вернуть «Демо» → `/demo`, «Методика» → `/#research` в обоих меню), `README.md`
- Create: `frontend/e2e/landing.spec.ts`
- Modify: `frontend/e2e/screens.spec.ts` (кадры лендинга и `/demo`)

- [ ] **Step 1: Падающий e2e**

`frontend/e2e/landing.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("landing → demo without login, and no request to the API (Review Focus 3)", async ({ page }) => {
  const api: string[] = [];
  page.on("request", r => { if (r.url().includes("/api/") && !r.url().endsWith("/api/capabilities")) api.push(r.url()); });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Сверка");
  await page.getByRole("link", { name: "Попробовать демо" }).first().click();
  await expect(page).toHaveURL(/\/demo$/);
  await expect(page.getByRole("heading", { level: 2, name: "Общая площадь, м²" })).toBeVisible({ timeout: 20_000 });
  await page.keyboard.press("1");
  await expect(page.getByText("1/4")).toBeVisible();
  expect(api).toEqual([]);
});

test("KZ is remembered after reload (Review Focus 5)", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "KZ" }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "kk");
});

test.describe("phone and reduced motion (Review Focus 4)", () => {
  test.use({ viewport: { width: 375, height: 812 }, reducedMotion: "reduce" });
  test("fallback frames, no side scroll", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("canvas")).toHaveCount(0);
    await expect(page.locator('svg[data-scene="fallback"]')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
});

test("access request is accepted", async ({ page }) => {
  await page.goto("/#access");
  await page.getByLabel("Почта").fill(`e2e-${Date.now()}@bureau.kz`);
  await page.getByLabel("Организация").fill("ТОО «Бюро»");
  await page.getByRole("button", { name: "Отправить заявку" }).click();
  await expect(page.getByRole("status")).toContainText("Спасибо");
});
```

(Подписи «Почта», «Организация», «Отправить заявку», «Спасибо…» — значения `access.email`, `access.org`, `access.send`, `access.done` в `RU`.)

Run: `cd frontend && npx playwright test landing` → FAIL на последнем незавершённом шаге, если что-то не готово; иначе — PASS после Step 2.

- [ ] **Step 2: Меню и README**

Sidebar — вернуть `<a href="/demo">` и `<a href="/#research">` (как в плане 1, Task 4) в боковое и мобильное меню. README, раздел «MVP»: `/` — лендинг, `/demo` — демо-отчёт без входа, `scripts/export_demo.py` пересобирает демо-данные, миграция `20261012120000_access_requests.sql` применяется до деплоя.

- [ ] **Step 3: Всё вместе**

Run:
```bash
npm --prefix frontend test
npm --prefix frontend run budget
(cd frontend && npx playwright test)
uv run pytest -q tests/test_api_store.py tests/test_export_demo.py tests/test_pipeline.py
```
Expected: всё PASS; бюджеты в пределах.

- [ ] **Step 4: Ручная проверка**

Скриншоты лендинга на 375 / 1366 / 1920 px, обе темы, RU и KZ, и `/demo`; просмотреть: сцена раздвигает этажи и рисует обводку при прокрутке, текст не перекрыт сценой, KZ не ломает вёрстку длинными словами.

- [ ] **Step 5: Commit**

```bash
git add -A frontend README.md
git commit -m "Лендинг готов: меню «Демо»/«Методика», e2e лендинга, README"
```

## Перед слиянием в `main`

- [ ] Применить миграцию `supabase/migrations/20261012120000_access_requests.sql`.
- [ ] Показать автору тексты блоков «Проблема» и «Исследование» (RU/KZ) — цифры и формулировки.
- [ ] Вычитка KZ носителем (можно после слияния; пометка в `landing/i18n.ts` остаётся до вычитки).
