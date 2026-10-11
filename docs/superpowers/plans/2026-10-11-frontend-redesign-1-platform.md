# Переделка фронтенда, план 1: основа и платформа — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перевести платформу (`/app`) на дизайн-систему «Чертёж», маршруты, оболочку с боковым меню, список проверок, мастер новой проверки, отчёт в три колонки и ⌘K — на существующем API и логике.

**Architecture:** Одно Vite + React приложение. React Router задаёт маршруты, TanStack Query — данные, Tailwind v4 на CSS-переменных — две темы «Калька» / «Синька». Существующая логика (PDF-просмотр, фильтры, вердикты, экспорт, загрузка, вход) переносится в `lib/` и `platform/` и меняет только вид и раскладку. Бэкенд получает список проверок и переименование.

**Tech Stack:** React 18.3, Vite 5, TypeScript 5.5, react-router 7, @tanstack/react-query 5, Tailwind CSS 4 (`@tailwindcss/vite`), Radix (`@radix-ui/react-dialog`), cmdk 1, Vitest + Testing Library + jsdom, Playwright; FastAPI + pytest на бэкенде.

**Spec:** `docs/superpowers/specs/2026-10-11-frontend-redesign-design.md` (разделы 2, 3, 5, 6, 7, 8; лендинг §4 и демо/заявки — в плане 2).

## Global Constraints

- Работа в ветке `frontend-redesign`, рабочая копия `.worktrees/frontend-redesign`; команды — из её корня.
- Новые npm-зависимости: точная версия (`--save-exact`), опубликованная не позже чем за 14 дней до установки. Выбор версии: `npm view <pkg> time --json` → самая новая стабильная (без `-`) с датой ≤ сегодня − 14 дней.
- Цвета только из токенов §3 спецификации; `pencil` — только расхождения; у статусных плашек всегда есть текст.
- Шрифты IBM Plex Sans / Sans Condensed / Mono (Google Fonts, `subset=cyrillic,cyrillic-ext`).
- Элементы управления не ниже 26 px; рамки элементов цветом `control` (≥ 3:1); фокус 2 px `blue`.
- Движение интерфейса 150–250 мс ease-out; при `prefers-reduced-motion: reduce` анимации отключены.
- Платформа не импортирует three.js / react-three-fiber.
- Анализ ТЭП (`src/`), формат отчёта и вход через Supabase не меняются.
- Тексты интерфейса — по-русски, через `lib/i18n.ts` (ключи), без строк прямо в JSX новых компонентов оболочки и страниц.
- Локально (без `SUPABASE_URL`) входа нет; с Supabase каждый `/api/checks…` идёт с токеном.

## Review Focus

1. **Замечание с одним местом или с тремя и больше** (`refs.length !== 2`) — панель справа показывает все значения, Δ % только для пары; не падает. → тест в Task 7.
2. **Проверка в статусе `error` / `receiving` / `pending`, открытая по ссылке** — отчётная страница показывает понятное состояние (ошибка / «загрузка не завершена» / «идёт проверка»), а не вечный спиннер. → тест в Task 7.
3. **Очень длинное название объекта** (казахские составные слова, 200 символов) — в таблице обрезается многоточием с полным текстом в `title`, вёрстка не ломается. → тест в Task 5.
4. **Отчёт без замечаний** (всё совпало) — левая колонка «Расхождений нет», правая — пустое состояние, клавиши `j`/`k`/`1`/`2` ничего не ломают. → тест в Task 7.
5. **Сессия истекла во время работы** (401 на сохранении вердикта или переименовании) — переход на `/login?next=<текущий путь>`, после входа — обратно. → тест в Task 4.

---

## Структура файлов

```
frontend/
  index.html                       — шрифты Plex, <html data-theme>
  vite.config.ts                   — + tailwindcss(), test (vitest)
  playwright.config.ts             — e2e (Task 9)
  e2e/platform.spec.ts             — e2e (Task 9)
  src/
    main.tsx                       — провайдеры + роутер
    test/setup.ts                  — jest-dom
    app/router.tsx                 — маршруты, редирект /?check=
    app/providers.tsx              — QueryClient, тема, вход
    design/
      tokens.css                   — CSS-переменные обеих тем
      index.css                    — @import tailwind, @theme, база, сетка кальки
      theme.ts                     — useTheme(): system | light | dark
      Button.tsx Badge.tsx SectionChip.tsx Kbd.tsx StampSummary.tsx
      EmptyState.tsx Toast.tsx Dialog.tsx
    lib/
      api.ts auth.ts types.ts labels.ts export.ts   — перенесены из src/ (git mv) + новые вызовы
      i18n.ts                      — словарь RU
      queries.ts                   — хуки TanStack Query
      reviewQueue.ts               — очередь сохранения вердиктов
    platform/
      shell/AppShell.tsx Sidebar.tsx CommandMenu.tsx RequireAuth.tsx
      auth/LoginPage.tsx           — Login + SetPassword (перенос)
      checks/ChecksPage.tsx ChecksTable.tsx
      new/NewCheckPage.tsx Stepper.tsx
      report/ReportPage.tsx FindingsColumn.tsx FindingDetail.tsx useReportKeys.ts
      report/findings.ts           — comparedLabel, Filter, applyFilter (из components/Findings.tsx)
      report/DocumentPane.tsx RefPane.tsx   — из components/Viewer.tsx, RefPane.tsx
      report/TepTab.tsx CompletenessTab.tsx FileReview.tsx
      settings/SettingsPage.tsx
api/main.py                        — GET /api/checks, PATCH /api/checks/{id}, SPA-фолбэк
api/_store.py                      — list_checks, set_title, title по умолчанию
supabase/migrations/20261011120000_checks_title.sql
vercel.json                        — SPA-переписывание
tests/test_api_store.py            — новые тесты
```

Удаляются в Task 9: `src/App.tsx`, `src/components/*`, `src/styles.css`, `src/api.ts` и др. корневые (после `git mv` в `lib/`).

---

### Task 1: Дизайн-система «Чертёж» и тестовая инфраструктура

**Files:**
- Modify: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/tsconfig.json`
- Create: `frontend/src/design/tokens.css`, `frontend/src/design/index.css`, `frontend/src/design/theme.ts`, `frontend/src/design/Button.tsx`, `frontend/src/design/Badge.tsx`, `frontend/src/design/SectionChip.tsx`, `frontend/src/design/Kbd.tsx`, `frontend/src/design/StampSummary.tsx`, `frontend/src/design/EmptyState.tsx`, `frontend/src/design/Toast.tsx`, `frontend/src/design/Dialog.tsx`, `frontend/src/test/setup.ts`
- Test: `frontend/src/design/design.test.tsx`

**Interfaces:**
- Produces:
  - `useTheme(): { theme: "system" | "light" | "dark"; resolved: "light" | "dark"; setTheme(t): void }` — пишет `data-theme` на `<html>`, хранит выбор в `localStorage["tep.theme"]` (в try/catch).
  - `<Button variant="primary" | "secondary" | "ghost" size?="sm" | "md" {...button props}>`
  - `<Badge kind="mismatch" | "missing" | "match" | "expert" | "scan" | "confirmed" | "false_positive">{text}</Badge>`
  - `<SectionChip section: Section present?: boolean />`
  - `<Kbd>{key}</Kbd>`
  - `<StampSummary items: { label: string; value: string; tone?: "bad" | "warn" | "ok" }[] />`
  - `<EmptyState title: string; children?; action?: ReactNode />`
  - `ToastProvider`, `useToast(): (text: string, tone?: "error" | "info") => void`
  - `<Dialog open onOpenChange title: string>{children}</Dialog>` (Radix)

- [ ] **Step 1: Установить зависимости и настроить Vitest**

Выбрать версии по правилу из Global Constraints, затем (подставив выбранные версии):

```bash
npm --prefix frontend install --save-exact tailwindcss@<v> @tailwindcss/vite@<v> @radix-ui/react-dialog@<v> clsx@<v>
npm --prefix frontend install --save-exact -D vitest@<v> jsdom@<v> @testing-library/react@<v> @testing-library/jest-dom@<v> @testing-library/user-event@<v>
```

`frontend/vite.config.ts`:

```ts
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
  test: { environment: "jsdom", setupFiles: ["src/test/setup.ts"], css: false, include: ["src/**/*.test.{ts,tsx}"] },
});
```

`frontend/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

В `frontend/package.json` → `"scripts"`: добавить `"test": "vitest run"`. Тесты импортируют `describe` / `it` / `expect` из `vitest` явно, глобальные типы не нужны.

- [ ] **Step 2: Написать падающий тест дизайн-системы**

`frontend/src/design/design.test.tsx`:

```tsx
import { act, render, renderHook, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import Badge from "./Badge";
import Button from "./Button";
import SectionChip from "./SectionChip";
import StampSummary from "./StampSummary";
import { useTheme } from "./theme";

describe("design system", () => {
  beforeEach(() => { localStorage.clear(); document.documentElement.removeAttribute("data-theme"); });

  it("theme defaults to system and persists an explicit choice", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("system");
    act(() => result.current.setTheme("dark"));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("tep.theme")).toBe("dark");
  });

  it("badges always carry text, not only colour", () => {
    render(<Badge kind="mismatch">Расхождение</Badge>);
    expect(screen.getByText("Расхождение")).toHaveAttribute("data-kind", "mismatch");
  });

  it("section chip marks a missing section", () => {
    render(<SectionChip section="KR" present={false} />);
    const chip = screen.getByText("КР");
    expect(chip).toHaveAttribute("data-present", "false");
    expect(chip).toHaveAttribute("title", "Конструктивные решения: нет в пакете");
  });

  it("stamp summary renders every item with its tone", () => {
    render(<StampSummary items={[{ label: "Расхождения", value: "3", tone: "bad" }, { label: "Разделы", value: "4/4" }]} />);
    expect(screen.getByText("3").closest("[data-tone]")).toHaveAttribute("data-tone", "bad");
    expect(screen.getByText("4/4")).toBeInTheDocument();
  });

  it("primary button is a real button with type=button by default", () => {
    render(<Button variant="primary">Начать</Button>);
    expect(screen.getByRole("button", { name: "Начать" })).toHaveAttribute("type", "button");
  });
});
```

- [ ] **Step 3: Запустить — убедиться, что падает**

Run: `npm --prefix frontend test -- src/design`
Expected: FAIL — модули `./Badge`, `./theme` и др. не найдены.

- [ ] **Step 4: Токены, тема, база Tailwind**

`frontend/src/design/tokens.css`:

```css
:root, [data-theme="light"] {
  --paper: #F4F6F3; --sheet: #FFFFFF; --ink: #1E2A2B; --ink-2: #55615E; --line: #C9D2CD; --control: #7F8C87;
  --blue: #1E3A8A; --blue-wash: #E6EAF5; --pencil: #B3122E; --pencil-wash: #F8E4E7;
  --amber: #8A5A00; --amber-wash: #F5EBD6; --green: #1F6B4A; --green-wash: #E3F0E9; --doc-bg: #DDE3DF;
  color-scheme: light;
}
[data-theme="dark"] {
  --paper: #0F1E3D; --sheet: #132548; --ink: #E6EDF7; --ink-2: #A9B8D1; --line: #2A4478; --control: #5D77A8;
  --blue: #8FB4FF; --blue-wash: #1B3260; --pencil: #FF6B7D; --pencil-wash: #3A1B33;
  --amber: #F2C46D; --amber-wash: #3A3020; --green: #6FD3A0; --green-wash: #163A33; --doc-bg: #0B1630;
  color-scheme: dark;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #0F1E3D; --sheet: #132548; --ink: #E6EDF7; --ink-2: #A9B8D1; --line: #2A4478; --control: #5D77A8;
    --blue: #8FB4FF; --blue-wash: #1B3260; --pencil: #FF6B7D; --pencil-wash: #3A1B33;
    --amber: #F2C46D; --amber-wash: #3A3020; --green: #6FD3A0; --green-wash: #163A33; --doc-bg: #0B1630;
    color-scheme: dark;
  }
}
```

`frontend/src/design/index.css`:

```css
@import "tailwindcss";
@import "./tokens.css";

@theme inline {
  --color-paper: var(--paper); --color-sheet: var(--sheet); --color-ink: var(--ink); --color-ink-2: var(--ink-2);
  --color-line: var(--line); --color-control: var(--control); --color-blue: var(--blue); --color-blue-wash: var(--blue-wash);
  --color-pencil: var(--pencil); --color-pencil-wash: var(--pencil-wash); --color-amber: var(--amber);
  --color-amber-wash: var(--amber-wash); --color-green: var(--green); --color-green-wash: var(--green-wash);
  --color-doc: var(--doc-bg);
  --font-sans: "IBM Plex Sans", Arial, sans-serif;
  --font-cond: "IBM Plex Sans Condensed", "Arial Narrow", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
  --radius-sm: 2px; --radius: 3px;
}

@layer base {
  html, body, #root { height: 100%; }
  body { background: var(--paper); color: var(--ink); font: 15px/1.5 var(--font-sans); }
  :focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }
  button, input, select, textarea { font: inherit; color: inherit; }
}

@layer utilities {
  .bg-tracing {
    background-color: var(--paper);
    background-image: linear-gradient(var(--line) 1px, transparent 1px), linear-gradient(90deg, var(--line) 1px, transparent 1px);
    background-size: 24px 24px; background-position: -1px -1px;
  }
  .num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
  .pencil-ring { position: absolute; border: 2.5px solid var(--pencil); border-radius: 46% 54% 48% 52% / 58% 44% 56% 42%;
    transform: rotate(-2deg); pointer-events: none; }
}

@media (prefers-reduced-motion: no-preference) {
  .pencil-ring { animation: pencil-draw .45s ease-out; }
  @keyframes pencil-draw { from { clip-path: inset(0 100% 0 0); } to { clip-path: inset(0 0 0 0); } }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration: 0ms !important; animation-duration: 0ms !important; }
}
```

`frontend/src/design/theme.ts`:

```ts
import { useCallback, useEffect, useState } from "react";

export type ThemeChoice = "system" | "light" | "dark";
const KEY = "tep.theme";

const read = (): ThemeChoice => {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch { return "system"; }
};
const systemDark = () => typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;

/** «Калька» / «Синька»: the explicit choice wins, otherwise the system setting. */
export function useTheme() {
  const [theme, setThemeState] = useState<ThemeChoice>(read);
  const resolved: "light" | "dark" = theme === "system" ? (systemDark() ? "dark" : "light") : theme;

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme"); else root.dataset.theme = theme;
  }, [theme]);

  const setTheme = useCallback((t: ThemeChoice) => {
    try { if (t === "system") localStorage.removeItem(KEY); else localStorage.setItem(KEY, t); } catch { /* blocked storage */ }
    setThemeState(t);
  }, []);

  return { theme, resolved, setTheme };
}
```

`frontend/index.html` — заменить `<link href=...Fira...>` на:

```html
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap&subset=cyrillic,cyrillic-ext" rel="stylesheet">
```

- [ ] **Step 5: Компоненты**

`frontend/src/design/Button.tsx`:

```tsx
import clsx from "clsx";
import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost"; size?: "sm" | "md" };

const VARIANT = {
  primary: "bg-blue text-sheet border-blue hover:opacity-90",
  secondary: "bg-sheet text-blue border-blue hover:bg-blue-wash",
  ghost: "bg-transparent text-ink-2 border-transparent hover:text-ink hover:bg-sheet",
};

export default function Button({ variant = "secondary", size = "md", type = "button", className, ...rest }: Props) {
  return (
    <button type={type} {...rest} className={clsx(
      "inline-flex items-center gap-1.5 border rounded font-semibold transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed",
      size === "sm" ? "min-h-[26px] px-2.5 text-[13px]" : "min-h-9 px-3.5 text-sm", VARIANT[variant], className)} />
  );
}
```

`frontend/src/design/Badge.tsx`:

```tsx
import clsx from "clsx";
import type { ReactNode } from "react";

export type BadgeKind = "mismatch" | "missing" | "match" | "expert" | "scan" | "confirmed" | "false_positive";
const KIND: Record<BadgeKind, string> = {
  mismatch: "text-pencil bg-pencil-wash border-pencil",
  missing: "text-amber bg-amber-wash border-amber",
  match: "text-green bg-green-wash border-green",
  expert: "text-blue bg-blue-wash border-blue",
  scan: "text-amber bg-amber-wash border-amber",
  confirmed: "text-green bg-green-wash border-green",
  false_positive: "text-ink-2 border-ink-2 line-through",
};

export default function Badge({ kind, children }: { kind: BadgeKind; children: ReactNode }) {
  return (
    <span data-kind={kind} className={clsx(
      "inline-block border rounded-sm px-1.5 py-px font-cond text-[11px] font-semibold uppercase tracking-wide", KIND[kind])}>
      {children}
    </span>
  );
}
```

`frontend/src/design/SectionChip.tsx`:

```tsx
import { SECTION, SECTION_FULL } from "../lib/labels";
import type { Section } from "../lib/types";

export default function SectionChip({ section, present = true }: { section: Section; present?: boolean }) {
  return (
    <span data-present={String(present)} title={`${SECTION_FULL[section]}${present ? "" : ": нет в пакете"}`}
      className={present
        ? "inline-grid place-items-center min-w-8 h-[22px] px-1 border border-ink rounded-sm font-cond text-[11.5px] font-semibold"
        : "inline-grid place-items-center min-w-8 h-[22px] px-1 border border-line text-ink-2 rounded-sm font-cond text-[11.5px] line-through"}>
      {SECTION[section]}
    </span>
  );
}
```

(Этот компонент импортирует `lib/labels` и `lib/types`: шаг 6 переносит их в `lib/`.)

`frontend/src/design/Kbd.tsx`:

```tsx
import type { ReactNode } from "react";

export default function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="font-mono text-[11px] border border-control border-b-2 rounded px-1 bg-sheet">{children}</kbd>;
}
```

`frontend/src/design/StampSummary.tsx`:

```tsx
import clsx from "clsx";

export interface StampItem { label: string; value: string; tone?: "bad" | "warn" | "ok" }
const TONE = { bad: "text-pencil", warn: "text-amber", ok: "text-green" };

/** The title-block of a drawing: key numbers of a check in one framed row. */
export default function StampSummary({ items }: { items: StampItem[] }) {
  return (
    <dl className="grid border-2 border-ink bg-sheet" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
      {items.map(it => (
        <div key={it.label} data-tone={it.tone ?? "none"} className="px-3 py-1.5 border-l border-ink first:border-l-0 min-w-0">
          <dt className="font-cond text-[11px] text-ink-2 truncate">{it.label}</dt>
          <dd className={clsx("num text-xl font-semibold", it.tone && TONE[it.tone])}>{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}
```

`frontend/src/design/EmptyState.tsx`:

```tsx
import type { ReactNode } from "react";

export default function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2 p-6 text-ink-2">
      <p className="text-ink font-semibold">{title}</p>
      {children && <div className="text-sm">{children}</div>}
      {action}
    </div>
  );
}
```

`frontend/src/design/Toast.tsx`:

```tsx
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Tone = "error" | "info";
interface Item { id: number; text: string; tone: Tone }
const Ctx = createContext<(text: string, tone?: Tone) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const push = useCallback((text: string, tone: Tone = "info") => {
    const id = Date.now() + Math.random();
    setItems(xs => [...xs, { id, text, tone }]);
    setTimeout(() => setItems(xs => xs.filter(x => x.id !== id)), 5000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div role="status" aria-live="polite" className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {items.map(t => (
          <div key={t.id} className={t.tone === "error"
            ? "bg-sheet border border-pencil text-pencil px-3 py-2 rounded shadow"
            : "bg-sheet border border-ink px-3 py-2 rounded shadow"}>{t.text}</div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);
```

`frontend/src/design/Dialog.tsx`:

```tsx
import * as D from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

export default function Dialog({ open, onOpenChange, title, children }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; children: ReactNode;
}) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 bg-black/30 z-40" />
        <D.Content className="fixed left-1/2 top-[15vh] -translate-x-1/2 z-50 w-[min(560px,calc(100vw-32px))] bg-sheet border border-ink rounded shadow-lg">
          <D.Title className="font-cond text-sm font-semibold uppercase tracking-wide text-ink-2 px-4 pt-3">{title}</D.Title>
          {children}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}
```

- [ ] **Step 6: Перенести общие модули в `lib/`**

```bash
cd frontend/src && mkdir -p lib && git mv api.ts auth.ts types.ts labels.ts export.ts lib/ && cd ../..
```

Поправить импорты в старых компонентах (они удаляются в Task 9, но до этого сборка должна проходить): во всех `frontend/src/components/*.tsx` и `frontend/src/App.tsx` заменить `from "../api"` → `from "../lib/api"`, `"../auth"` → `"../lib/auth"`, `"../types"` → `"../lib/types"`, `"../labels"` → `"../lib/labels"`, `"../export"` → `"../lib/export"`; в `App.tsx` — `"./api"` → `"./lib/api"` и т.д. В `lib/export.ts` поменять `from "./components/Findings"` → `from "../components/Findings"` и `from "./components/ReviewBar"` → `from "../components/ReviewBar"`.

Проверка: `npx --prefix frontend tsc -b frontend` без ошибок.

- [ ] **Step 7: Подключить стили в `main.tsx`**

`frontend/src/main.tsx` — заменить `import "./styles.css";` на:

```ts
import "./styles.css"; // старый интерфейс, удаляется в Task 9
import "./design/index.css";
```

- [ ] **Step 8: Запустить тесты — должны пройти**

Run: `npm --prefix frontend test -- src/design`
Expected: PASS (5 тестов).

- [ ] **Step 9: Commit**

```bash
git add frontend
git commit -m "Дизайн-система «Чертёж»: токены двух тем, Tailwind, компоненты; Vitest"
```

---

### Task 2: Бэкенд — список проверок, переименование, SPA-маршруты

**Files:**
- Modify: `api/_store.py`, `api/main.py`, `vercel.json`
- Create: `supabase/migrations/20261011120000_checks_title.sql`
- Test: `tests/test_api_store.py`

**Interfaces:**
- Produces:
  - `GET /api/checks` → `{"checks": [CheckRow]}`, новые сверху, только свои (без входа — все локальные);
    `CheckRow = {"id": str, "title": str, "status": "receiving"|"uploaded"|"pending"|"done"|"error", "created_at": ISO-8601 str, "sections": ["PZ"|"AR"|"KR"|"SMETA"], "summary": {"MISMATCH": int, "MISSING": int, "MATCH": int} | null, "reviewed": int, "expires_at": ISO-8601 str}`
  - `PATCH /api/checks/{id}` body `{"title": str (1–200, после strip)}` → `{"id", "title"}`; чужая/нет — 404; пустое/длинное — 422.
  - `default_title(report: dict, files: list[str]) -> str` в `api/main.py`.
  - Store: `list_checks(owner: str | None) -> list[dict]`, `set_title(check_id, title) -> None`, `title` в `get()`.

- [ ] **Step 1: Написать падающие тесты**

Дописать в `tests/test_api_store.py`:

```python
def test_list_checks_shows_own_newest_first_with_summary(authed):
    first = authed.post("/api/demo/ru", headers=A).json()["id"]
    time.sleep(0.01)
    second = authed.post("/api/demo/kz", headers=A).json()["id"]
    authed.post("/api/demo/ru", headers=B)  # someone else's
    for cid in (first, second):
        for _ in range(200):
            if authed.get(f"/api/checks/{cid}", headers=A).json()["status"] == "done":
                break
            time.sleep(0.05)
    authed.put(f"/api/checks/{first}/reviews/0", json={"verdict": "confirmed"}, headers=A)
    rows = authed.get("/api/checks", headers=A).json()["checks"]
    assert [r["id"] for r in rows] == [second, first]
    row = rows[1]
    assert row["status"] == "done" and row["summary"]["MISMATCH"] == 3
    assert set(row["sections"]) == {"PZ", "AR", "KR", "SMETA"}
    assert row["reviewed"] == 1 and row["title"] and row["expires_at"] > row["created_at"]


def test_list_checks_needs_login(authed):
    assert authed.get("/api/checks").status_code == 401


def test_rename_check(authed):
    cid = authed.post("/api/demo/ru", headers=A).json()["id"]
    r = authed.patch(f"/api/checks/{cid}", json={"title": "  ЖК «Алатау», блок 2  "}, headers=A)
    assert r.status_code == 200 and r.json()["title"] == "ЖК «Алатау», блок 2"
    assert authed.get(f"/api/checks/{cid}", headers=A).json()["title"] == "ЖК «Алатау», блок 2"
    assert authed.patch(f"/api/checks/{cid}", json={"title": "x"}, headers=B).status_code == 404
    assert authed.patch(f"/api/checks/{cid}", json={"title": "   "}, headers=A).status_code == 422
    assert authed.patch(f"/api/checks/{cid}", json={"title": "я" * 201}, headers=A).status_code == 422


def test_default_title_prefers_the_object_of_the_explanatory_note():
    from api.main import default_title
    report = {"objects": {"b1": "Жилой дом №1"}, "pz_building": "b1", "documents": []}
    assert default_title(report, ["PZ.pdf"]) == "Жилой дом №1"
    report = {"objects": {}, "pz_building": None, "documents": [{"file": "ПЗ Школа.pdf", "section": "PZ"}]}
    assert default_title(report, ["ПЗ Школа.pdf"]) == "ПЗ Школа"
    assert default_title({}, ["a.pdf", "b.pdf"]) == "a.pdf и ещё 1"


def test_spa_routes_serve_the_interface(client):
    for path in ("/app", "/app/checks/" + "a" * 32, "/login"):
        r = client.get(path)
        assert r.status_code == 200 and "<" in r.text
    assert client.get("/api/nope").status_code == 404
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `uv run pytest -q tests/test_api_store.py -k "list_checks or rename or default_title or spa_routes"`
Expected: FAIL (404 / ImportError `default_title`).

- [ ] **Step 3: Миграция Supabase**

`supabase/migrations/20261011120000_checks_title.sql`:

```sql
alter table public.checks add column if not exists title text check (title is null or length(title) between 1 and 200);
comment on column public.checks.title is 'Название проверки (объект из ПЗ по умолчанию, можно переименовать).';
```

- [ ] **Step 4: Хранилища**

В `api/_store.py`, класс `LocalStore` — добавить (рядом с `get`):

```python
    def set_title(self, check_id: str, title: str) -> None:
        meta_path = self._dir(check_id) / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        meta["title"] = title
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    def list_checks(self, owner: str | None) -> list[dict]:
        rows = []
        if not self.root.is_dir():
            return rows
        for d in self.root.iterdir():
            status = self.get(d.name) if (d / "status.json").is_file() else None
            if status is None or (owner is not None and status.get("owner") != owner):
                continue
            meta_path = d / "meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
            created = meta.get("created_at") or datetime.fromtimestamp(d.stat().st_mtime, UTC).isoformat()
            report = status.get("report") or {}
            rows.append({
                "id": d.name, "title": status.get("title"), "status": status["status"], "created_at": created,
                "sections": (report.get("completeness") or {}).get("present", []),
                "summary": report.get("summary"), "reviewed": sum(1 for r in self.reviews(d.name).values() if r["verdict"]),
                "files": self.names(d.name),
            })
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)
```

и в `LocalStore.get` — после строки, где читается `owner` из `meta.json`, добавить чтение названия:

```python
        status["title"] = json.loads(meta.read_text(encoding="utf-8")).get("title") if meta.is_file() else None
```

В `LocalStore.create` — в словарь `meta.json` добавить `"title": None, "created_at": datetime.now(UTC).isoformat()` (дата создания не должна зависеть от времени изменения файла: переименование переписывает `meta.json`).

Класс `SupabaseStore` — добавить:

```python
    def set_title(self, check_id: str, title: str) -> None:
        self._set(check_id, title=title)

    def list_checks(self, owner: str | None) -> list[dict]:
        query = ("?select=id,title,status,created_at,files,summary:report->summary,"
                 "present:report->completeness->present&order=created_at.desc&limit=200")
        if owner is not None:
            query += f"&owner=eq.{owner}"
        rows = self._rows("GET", query).json()
        reviewed: dict[str, int] = {}
        if rows:
            ids = ",".join(r["id"] for r in rows)
            for rv in self._rows("GET", f"?check_id=in.({ids})&verdict=not.is.null&select=check_id", table="reviews").json():
                reviewed[rv["check_id"]] = reviewed.get(rv["check_id"], 0) + 1
        return [{"id": r["id"], "title": r["title"], "status": r["status"], "created_at": r["created_at"],
                 "sections": r["present"] or [], "summary": r["summary"], "reviewed": reviewed.get(r["id"], 0),
                 "files": r["files"]} for r in rows]
```

и в `SupabaseStore.get`: в `select=` добавить `title`, в результат — `"title": row["title"]`.

- [ ] **Step 5: Эндпоинты и название по умолчанию**

В `api/main.py` — после `_owned` добавить:

```python
def default_title(report: dict, files: list[str]) -> str:
    """The object of the explanatory note, else the note's file name, else the first file."""
    objects, building = report.get("objects") or {}, report.get("pz_building")
    if building and objects.get(building):
        return objects[building][:200]
    pz = next((d["file"] for d in report.get("documents", []) if d.get("section") == "PZ"), None)
    if pz:
        return Path(pz).stem[:200]
    if not files:
        return "Проверка"
    return files[0] if len(files) == 1 else f"{files[0]} и ещё {len(files) - 1}"
```

В `_run` — после `store.finish(check_id, "done", report=report)`:

```python
        if not (store.get(check_id) or {}).get("title"):
            store.set_title(check_id, default_title(report, store.names(check_id)))
```

Новые эндпоинты (перед `@app.put("/api/checks/{check_id}/reviews/{finding}")`):

```python
@app.get("/api/checks")
def list_checks(user: str | None = User) -> dict:
    rows = _store().list_checks(user)
    for r in rows:
        if not r["title"]:
            r["title"] = default_title({}, r.pop("files", []))
        else:
            r.pop("files", None)
        created = datetime.fromisoformat(r["created_at"])
        r["expires_at"] = (created + timedelta(days=RETENTION_DAYS)).isoformat()
    return {"checks": rows}


class Rename(BaseModel):
    title: str = Field(max_length=400)


@app.patch("/api/checks/{check_id}")
def rename_check(check_id: str, body: Rename, user: str | None = User) -> dict:
    store = _store()
    _owned(store, check_id, user)
    title = body.title.strip()
    if not 1 <= len(title) <= 200:
        raise HTTPException(422, "название: от 1 до 200 символов")
    store.set_title(check_id, title)
    return {"id": check_id, "title": title}
```

Импорт: `from datetime import datetime, timedelta`. В `get_check` — ничего не менять (`title` приходит из `store.get`, `owner` уже удаляется в `_owned`).

SPA-фолбэк — заменить функцию `index()` на маршрут, отдающий `index.html` для всех путей не из `/api` и `/assets`:

```python
@app.get("/{path:path}", response_class=HTMLResponse, include_in_schema=False)
def spa(path: str) -> str:
    if path.startswith(("api/", "assets/")):
        raise HTTPException(404, "not found")
    page = FRONTEND / "index.html"
    if page.is_file():
        return page.read_text(encoding="utf-8")
    return ("<p>Интерфейс не собран: выполните <code>npm --prefix frontend ci</code> и "
            "<code>npm --prefix frontend run build</code> или запустите <code>npm --prefix frontend run dev</code> "
            "и откройте http://localhost:5173.</p>")
```

Этот маршрут должен идти **последним** в файле (после `app.mount("/assets", ...)`).

`vercel.json` — в `"rewrites"` после правила `/api/:path*` добавить:

```json
{ "source": "/((?!api/|assets/|demo/).*)", "destination": "/index.html" }
```

- [ ] **Step 6: Запустить тесты — должны пройти**

Run: `uv run ruff check api tests/test_api_store.py && uv run pytest -q tests/test_api_store.py tests/test_pipeline.py`
Expected: все PASS.

- [ ] **Step 7: Commit**

```bash
git add api tests/test_api_store.py vercel.json supabase
git commit -m "API: список своих проверок, переименование, название по умолчанию, SPA-маршруты"
```

---

### Task 3: Данные — API-клиент, хуки TanStack Query, очередь вердиктов, словарь

**Files:**
- Modify: `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`, `frontend/package.json`
- Create: `frontend/src/lib/queries.ts`, `frontend/src/lib/reviewQueue.ts`, `frontend/src/lib/i18n.ts`
- Test: `frontend/src/lib/lib.test.ts`

**Interfaces:**
- Consumes: `apiFetch`, `Unauthorized`, `saveReview` (lib/api.ts, уже есть).
- Produces:
  - `lib/types.ts`: `export interface CheckRow { id: string; title: string; status: "receiving" | "uploaded" | "pending" | "done" | "error"; created_at: string; sections: Section[]; summary: Record<Verdict, number> | null; reviewed: number; expires_at: string }`; в `CheckStatus` (вариант `done`) добавить `title?: string`.
  - `lib/api.ts`: `listChecks(): Promise<CheckRow[]>`, `renameCheck(id: string, title: string): Promise<string>`, `getCheck(id: string): Promise<CheckStatus>` (один запрос, без опроса; 404 → `Error("Проверка не найдена")`).
  - `lib/reviewQueue.ts`: `createReviewQueue(save: (finding: number, r: Review) => Promise<void>): { push(finding: number, r: Review): Promise<void> }` — сохранения одного замечания идут строго по очереди, промежуточные (ещё не начатые) схлопываются в последнее.
  - `lib/queries.ts`: `useChecks()`, `useCheck(id)` (refetch каждые 1000 мс, пока `status` ∈ {`receiving`, `pending`}), `useRenameCheck()`, `queryClient` (с `onError: toLogin` у кэшей запросов и мутаций), `toLogin(e: unknown): void` — при `Unauthorized` переход на `/login?next=<путь>`.
  - `lib/i18n.ts`: `t(key: Key, vars?: Record<string, string | number>): string`, `type Key` — ключи словаря RU.

- [ ] **Step 1: Установить TanStack Query**

```bash
npm --prefix frontend install --save-exact @tanstack/react-query@<v>
```

- [ ] **Step 2: Написать падающие тесты**

`frontend/src/lib/lib.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { t } from "./i18n";
import { createReviewQueue } from "./reviewQueue";
import type { Review } from "./types";

const r = (verdict: Review["verdict"], comment = ""): Review => ({ verdict, comment });

describe("review queue", () => {
  it("saves one finding strictly in order and collapses waiting saves into the last", async () => {
    const calls: string[] = [];
    let release!: () => void;
    const save = vi.fn((finding: number, rv: Review) => {
      calls.push(`${finding}:${rv.verdict}`);
      return calls.length === 1 ? new Promise<void>(res => { release = res; }) : Promise.resolve();
    });
    const q = createReviewQueue(save);
    const a = q.push(0, r("confirmed"));
    const b = q.push(0, r("false_positive"));
    const c = q.push(0, r(null));
    release();
    await Promise.all([a, b, c]);
    expect(calls).toEqual(["0:confirmed", "0:null"]);
  });

  it("different findings do not wait for each other", async () => {
    const save = vi.fn(() => new Promise<void>(() => {})); // never resolves
    const q = createReviewQueue(save);
    q.push(0, r("confirmed"));
    q.push(1, r("confirmed"));
    expect(save).toHaveBeenCalledTimes(2);
  });

  it("a failed save rejects its promise and the next one still runs", async () => {
    const save = vi.fn().mockRejectedValueOnce(new Error("500")).mockResolvedValue(undefined);
    const q = createReviewQueue(save);
    await expect(q.push(0, r("confirmed"))).rejects.toThrow("500");
    await expect(q.push(0, r("false_positive"))).resolves.toBeUndefined();
  });
});

describe("i18n", () => {
  it("substitutes variables", () => {
    expect(t("checks.count", { n: 4 })).toBe("Мои проверки · 4");
  });
});
```

- [ ] **Step 3: Запустить — убедиться, что падают**

Run: `npm --prefix frontend test -- src/lib`
Expected: FAIL — модули не найдены.

- [ ] **Step 4: Реализация**

`frontend/src/lib/reviewQueue.ts`:

```ts
import type { Review } from "./types";

/** Saves of one finding run one after another; saves still waiting are replaced by the newest,
 * so quick repeated clicks end in the last choice and a failed save cannot overwrite a later one. */
export function createReviewQueue(save: (finding: number, r: Review) => Promise<void>) {
  const running = new Map<number, Promise<void>>();
  const waiting = new Map<number, { review: Review; resolvers: { ok: () => void; fail: (e: unknown) => void }[] }>();

  const run = (finding: number, review: Review): Promise<void> => {
    const p = save(finding, review).finally(() => {
      running.delete(finding);
      const next = waiting.get(finding);
      if (next) {
        waiting.delete(finding);
        run(finding, next.review).then(() => next.resolvers.forEach(x => x.ok()), e => next.resolvers.forEach(x => x.fail(e)));
      }
    });
    running.set(finding, p);
    return p;
  };

  return {
    push(finding: number, review: Review): Promise<void> {
      if (!running.has(finding)) return run(finding, review);
      return new Promise<void>((ok, fail) => {
        const w = waiting.get(finding);
        if (w) { w.review = review; w.resolvers.push({ ok, fail }); }
        else waiting.set(finding, { review, resolvers: [{ ok, fail }] });
      });
    },
  };
}
```

`frontend/src/lib/i18n.ts`:

```ts
const RU = {
  "app.name": "ТЭП·Сверка",
  "nav.checks": "Проверки", "nav.new": "Новая проверка", "nav.demo": "Демо", "nav.method": "Методика", "nav.settings": "Настройки",
  "search.placeholder": "Найти проверку или замечание…", "search.hint": "Поиск",
  "checks.count": "Мои проверки · {n}", "checks.empty": "Проверок пока нет",
  "checks.empty.body": "Загрузите ПЗ, АР, КР и смету — или посмотрите демо-отчёт.",
  "checks.col.title": "Объект", "checks.col.sections": "Разделы", "checks.col.result": "Итог",
  "checks.col.expert": "Эксперт", "checks.col.date": "Дата", "checks.col.expires": "Хранится до",
  "checks.status.pending": "идёт проверка…", "checks.status.receiving": "загрузка не завершена",
  "checks.status.uploaded": "ждёт запуска", "checks.status.error": "ошибка",
  "checks.rename": "Переименовать", "checks.rename.save": "Сохранить",
  "new.step.files": "Файлы", "new.step.sections": "Разделы", "new.step.run": "Проверка",
  "new.drop": "Перетащите ПЗ, АР, КР и смету сюда или выберите файлы", "new.drop.hint": "PDF или DOCX, до 20 файлов по 50 МБ",
  "new.uploading": "Загружаем: {sent} из {total} МБ", "new.running": "Сверяем разделы…",
  "report.tab.findings": "Замечания", "report.tab.tep": "ТЭП", "report.tab.completeness": "Комплектность",
  "report.none": "Расхождений между разделами не найдено.", "report.detail.empty": "Выберите замечание слева",
  "report.export": "Скачать XLSX", "report.split": "Рядом", "report.single": "По одному",
  "report.pending": "Идёт проверка документов…", "report.receiving": "Загрузка файлов не была завершена. Загрузите документы заново.",
  "report.error": "Проверка не выполнена: {error}", "report.missing": "Проверка не найдена или удалена.",
  "verdict.confirm": "Подтверждаю", "verdict.false": "Ложное", "verdict.comment": "Комментарий",
  "settings.theme": "Тема", "settings.theme.system": "Как в системе", "settings.theme.light": "Калька (светлая)",
  "settings.theme.dark": "Синька (тёмная)", "settings.account": "Аккаунт", "settings.password": "Сменить пароль",
  "settings.password.sent": "Письмо со ссылкой для нового пароля отправлено на вашу почту.",
  "settings.signout": "Выйти",
  "cmd.new": "Новая проверка", "cmd.export": "Скачать XLSX", "cmd.theme": "Переключить тему", "cmd.signout": "Выйти",
  "cmd.go.check": "Проверка", "cmd.go.finding": "Замечание",
} as const;

export type Key = keyof typeof RU;

export function t(key: Key, vars: Record<string, string | number> = {}): string {
  return RU[key].replace(/\{(\w+)\}/g, (_, v) => String(vars[v] ?? ""));
}
```

В `frontend/src/lib/types.ts` — добавить `CheckRow` (как в Interfaces) и `title?: string` в вариант `status: "done"` типа `CheckStatus`.

В `frontend/src/lib/api.ts` — добавить:

```ts
export async function listChecks(): Promise<CheckRow[]> {
  return (await json<{ checks: CheckRow[] }>(apiFetch("/api/checks"), "Список проверок не загрузился.")).checks;
}

export async function renameCheck(id: string, title: string): Promise<string> {
  return (await json<{ title: string }>(apiFetch(`/api/checks/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }),
  }), "Название не сохранено.")).title;
}

export async function getCheck(id: string): Promise<CheckStatus> {
  const r = await apiFetch(`/api/checks/${id}`);
  if (r.status === 404) throw new Error("Проверка не найдена");
  if (!r.ok) throw new Error(`Сервер ответил ${r.status}`);
  return r.json();
}
```

(и `CheckRow` в импорт типов).

`frontend/src/lib/queries.ts`:

```ts
import { MutationCache, QueryCache, QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getCheck, listChecks, renameCheck, Unauthorized } from "./api";

/** Any request refused for login sends the user to /login and back here afterwards. */
export function toLogin(e: unknown): void {
  if (e instanceof Unauthorized && !location.pathname.startsWith("/login"))
    location.assign("/login?next=" + encodeURIComponent(location.pathname + location.search));
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: toLogin }),
  mutationCache: new MutationCache({ onError: toLogin }),
  defaultOptions: { queries: { retry: (n, e) => !(e instanceof Unauthorized) && n < 2, refetchOnWindowFocus: false } },
});

export const useChecks = () => useQuery({ queryKey: ["checks"], queryFn: listChecks });

export const useCheck = (id: string) => useQuery({
  queryKey: ["check", id],
  queryFn: () => getCheck(id),
  refetchInterval: q => (q.state.data && ["receiving", "pending"].includes(q.state.data.status) ? 1000 : false),
});

export function useRenameCheck() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameCheck(id, title),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["checks"] }); },
  });
}
```

- [ ] **Step 5: Запустить тесты — должны пройти**

Run: `npm --prefix frontend test -- src/lib && npx --prefix frontend tsc -b frontend`
Expected: PASS (4 теста), без ошибок типов.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "Данные: список и переименование проверок, хуки TanStack Query, очередь вердиктов, словарь RU"
```

---

### Task 4: Маршруты, оболочка, вход, настройки

**Files:**
- Create: `frontend/src/app/router.tsx`, `frontend/src/app/providers.tsx`, `frontend/src/platform/shell/AppShell.tsx`, `frontend/src/platform/shell/Sidebar.tsx`, `frontend/src/platform/shell/RequireAuth.tsx`, `frontend/src/platform/auth/LoginPage.tsx`, `frontend/src/platform/settings/SettingsPage.tsx`
- Move: `frontend/src/components/Login.tsx` → `frontend/src/platform/auth/Login.tsx`, `frontend/src/components/SetPassword.tsx` → `frontend/src/platform/auth/SetPassword.tsx`
- Modify: `frontend/src/main.tsx`, `frontend/package.json`
- Test: `frontend/src/app/router.test.tsx`

**Interfaces:**
- Consumes: `initAuth`, `authEnabled`, `currentEmail`, `authRedirect`, `signIn`, `signOut`, `setPassword`, `requestPasswordReset`, `onSignedOut` (lib/auth.ts); `getCapabilities` (lib/api.ts); `queryClient` (lib/queries.ts); `ToastProvider` (design).
- Produces:
  - `AuthState` (React context из `providers.tsx`): `useSession(): { ready: boolean; enabled: boolean; email: string | null; ocr: boolean; signOut(): Promise<void>; refresh(): Promise<void> }`.
  - `<RequireAuth>` — без сессии (при `enabled`) → `<Navigate to={"/login?next=" + encodeURIComponent(path)} />`.
  - Маршруты: `/` → `<Navigate to="/app" />` (лендинг — план 2), `/login`, `/app` (оболочка: `index` → ChecksPage, `new`, `checks/:id`, `settings`). Ссылка `/?check=<id>` → `/app/checks/<id>`.
  - Ошибка `Unauthorized` из любого запроса/мутации → `/login?next=<текущий путь>` (обработчик `toLogin` из Task 3 уже стоит в `queryClient`).

- [ ] **Step 1: Установить роутер**

```bash
npm --prefix frontend install --save-exact react-router@<v>
```

- [ ] **Step 2: Написать падающие тесты**

`frontend/src/app/router.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { legacyRedirect, routes } from "./router";
import { SessionContext, type Session } from "./providers";

const session = (over: Partial<Session> = {}): Session => ({
  ready: true, enabled: true, email: null, ocr: true, signOut: vi.fn(), refresh: vi.fn(), ...over,
});

function at(path: string, s: Session) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<SessionContext.Provider value={s}><RouterProvider router={router} /></SessionContext.Provider>);
  return router;
}

describe("routes", () => {
  it("old ?check= links open the report", () => {
    expect(legacyRedirect("?check=" + "a".repeat(32))).toBe("/app/checks/" + "a".repeat(32));
    expect(legacyRedirect("?check=../etc")).toBeNull();
    expect(legacyRedirect("")).toBeNull();
  });

  it("signed-out user is sent to login with the way back", () => {
    const router = at("/app/checks/" + "b".repeat(32), session());
    expect(router.state.location.pathname).toBe("/login");
    expect(router.state.location.search).toBe("?next=" + encodeURIComponent("/app/checks/" + "b".repeat(32)));
  });

  it("without auth (local run) the app opens directly", async () => {
    at("/app/settings", session({ enabled: false }));
    expect(await screen.findByRole("heading", { name: "Настройки" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Запустить — убедиться, что падают**

Run: `npm --prefix frontend test -- src/app`
Expected: FAIL — модули не найдены.

- [ ] **Step 4: Провайдеры и сессия**

`frontend/src/app/providers.tsx`:

```tsx
import { QueryClientProvider } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ToastProvider } from "../design/Toast";
import { getCapabilities } from "../lib/api";
import { authEnabled, currentEmail, initAuth, onSignedOut, signOut as authSignOut } from "../lib/auth";
import { queryClient } from "../lib/queries";

export interface Session {
  ready: boolean; enabled: boolean; email: string | null; ocr: boolean;
  signOut(): Promise<void>; refresh(): Promise<void>;
}
export const SessionContext = createContext<Session>({
  ready: false, enabled: false, email: null, ocr: true, signOut: async () => {}, refresh: async () => {},
});
export const useSession = () => useContext(SessionContext);

export function Providers({ children }: { children: ReactNode }) {
  const [state, setState] = useState({ ready: false, enabled: false, email: null as string | null, ocr: true });

  const refresh = useCallback(async () => {
    setState(s => ({ ...s, ready: true, enabled: authEnabled() }));
    const email = await currentEmail();
    setState(s => ({ ...s, email }));
  }, []);

  useEffect(() => {
    let off = () => {};
    (async () => {
      const caps = await getCapabilities();
      await initAuth(caps.auth);
      off = onSignedOut(() => setState(s => ({ ...s, email: null })));
      setState(s => ({ ...s, ocr: caps.ocr }));
      await refresh();
    })();
    return () => off();
  }, [refresh]);

  const session: Session = { ...state, signOut: async () => { await authSignOut(); queryClient.clear(); }, refresh };
  return (
    <QueryClientProvider client={queryClient}>
      <SessionContext.Provider value={session}>
        <ToastProvider>{children}</ToastProvider>
      </SessionContext.Provider>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 5: Роутер, защита, оболочка, вход, настройки**

`frontend/src/app/router.tsx`:

```tsx
import { lazy, Suspense } from "react";
import { Navigate, type RouteObject } from "react-router";
import AppShell from "../platform/shell/AppShell";
import RequireAuth from "../platform/shell/RequireAuth";
import LoginPage from "../platform/auth/LoginPage";
import SettingsPage from "../platform/settings/SettingsPage";

const ChecksPage = lazy(() => import("../platform/checks/ChecksPage"));
const NewCheckPage = lazy(() => import("../platform/new/NewCheckPage"));
const ReportPage = lazy(() => import("../platform/report/ReportPage"));
const page = (el: JSX.Element) => <Suspense fallback={<p className="p-6 text-ink-2">Загрузка…</p>}>{el}</Suspense>;

const ID_RE = /^[0-9a-f]{32}$/;
/** `/?check=<id>` links from the old interface. */
export function legacyRedirect(search: string): string | null {
  const id = new URLSearchParams(search).get("check");
  return id && ID_RE.test(id) ? `/app/checks/${id}` : null;
}

function Root() {
  return <Navigate to={legacyRedirect(location.search) ?? "/app"} replace />;
}

export const routes: RouteObject[] = [
  { path: "/", element: <Root /> },
  { path: "/login", element: <LoginPage /> },
  {
    path: "/app",
    element: <RequireAuth><AppShell /></RequireAuth>,
    children: [
      { index: true, element: page(<ChecksPage />) },
      { path: "new", element: page(<NewCheckPage />) },
      { path: "checks/:id", element: page(<ReportPage />) },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/app" replace /> },
];
```

`frontend/src/platform/shell/RequireAuth.tsx`:

```tsx
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { useSession } from "../../app/providers";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const s = useSession();
  const loc = useLocation();
  if (!s.ready) return <p className="p-6 text-ink-2">Загрузка…</p>;
  if (s.enabled && !s.email) return <Navigate to={"/login?next=" + encodeURIComponent(loc.pathname + loc.search)} replace />;
  return <>{children}</>;
}
```

`frontend/src/platform/shell/Sidebar.tsx`:

```tsx
import { NavLink } from "react-router";
import { t } from "../../lib/i18n";

const item = ({ isActive }: { isActive: boolean }) =>
  "block rounded px-2.5 py-1.5 text-sm " + (isActive ? "bg-[#2c3b3c] text-white" : "text-[#cfd8d4] hover:text-white");

export default function Sidebar() {
  return (
    <nav aria-label="Разделы" className="w-52 shrink-0 bg-[#1E2A2B] p-3 flex flex-col gap-0.5">
      <p className="font-cond font-semibold text-white px-2.5 pb-3">{t("app.name")}</p>
      <NavLink to="/app" end className={item}>{t("nav.checks")}</NavLink>
      <NavLink to="/app/new" className={item}>+ {t("nav.new")}</NavLink>
      <a href="/demo" className={item({ isActive: false })}>{t("nav.demo")}</a>
      <a href="/#research" className={item({ isActive: false })}>{t("nav.method")}</a>
      <span className="flex-1" />
      <NavLink to="/app/settings" className={item}>{t("nav.settings")}</NavLink>
    </nav>
  );
}
```

`frontend/src/platform/shell/AppShell.tsx` (CommandMenu подключается в Task 8; пока — кнопка-заглушка поиска не нужна, шапка только с почтой):

```tsx
import { Outlet } from "react-router";
import { useSession } from "../../app/providers";
import Sidebar from "./Sidebar";

export default function AppShell() {
  const s = useSession();
  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex-1 min-w-0 flex flex-col bg-tracing">
        <header className="flex items-center gap-3 px-4 h-12 bg-sheet border-b border-line">
          <span id="shell-search" className="flex-1" />
          {s.email && <span className="text-sm text-ink-2 truncate max-w-64" title={s.email}>{s.email}</span>}
        </header>
        <main className="flex-1 min-h-0 overflow-auto"><Outlet /></main>
      </div>
    </div>
  );
}
```

Переместить вход:

```bash
git mv frontend/src/components/Login.tsx frontend/src/platform/auth/Login.tsx
git mv frontend/src/components/SetPassword.tsx frontend/src/platform/auth/SetPassword.tsx
```

`frontend/src/platform/auth/LoginPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import { useSession } from "../../app/providers";
import { authRedirect, currentEmail, requestPasswordReset, setPassword, signIn } from "../../lib/auth";
import Login from "./Login";
import SetPassword from "./SetPassword";

/** Sign-in, and the "set a password" step after an invitation or reset link. */
export default function LoginPage() {
  const s = useSession();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next")?.startsWith("/app") ? params.get("next")! : "/app";
  const [email, setEmail] = useState<string | null>(null);
  useEffect(() => { currentEmail().then(setEmail); }, [s.email]);

  if (!s.ready) return <p className="p-6 text-ink-2">Загрузка…</p>;
  if (!s.enabled) return <Navigate to={next} replace />;
  const link = authRedirect();
  if (email && link.kind) {
    return <SetPassword email={email} invited={link.kind === "invite"}
      onSet={async p => { await setPassword(p); await s.refresh(); nav(next, { replace: true }); }} />;
  }
  if (s.email) return <Navigate to={next} replace />;
  return <Login notice={link.error}
    onSignIn={async (e, p) => { await signIn(e, p); await s.refresh(); nav(next, { replace: true }); }}
    onReset={requestPasswordReset} />;
}
```

(Старые `Login`/`SetPassword` используют классы старого CSS; в Task 9 их разметка переводится на Tailwind — классы `intake login` заменяются на `max-w-md mx-auto my-[10vh] px-4`, поля — `min-h-9 border border-control rounded px-2.5 bg-sheet`.)

`frontend/src/platform/settings/SettingsPage.tsx`:

```tsx
import { useSession } from "../../app/providers";
import Button from "../../design/Button";
import { useTheme, type ThemeChoice } from "../../design/theme";
import { useToast } from "../../design/Toast";
import { requestPasswordReset } from "../../lib/auth";
import { t } from "../../lib/i18n";

export default function SettingsPage() {
  const s = useSession();
  const toast = useToast();
  const { theme, setTheme } = useTheme();
  const opts: [ThemeChoice, string][] = [["system", t("settings.theme.system")], ["light", t("settings.theme.light")], ["dark", t("settings.theme.dark")]];
  return (
    <section className="max-w-xl p-6 flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">{t("nav.settings")}</h1>
      <fieldset className="flex flex-col gap-2">
        <legend className="font-cond text-xs uppercase tracking-wide text-ink-2 mb-1">{t("settings.theme")}</legend>
        {opts.map(([v, label]) => (
          <label key={v} className="flex items-center gap-2 min-h-[26px]">
            <input type="radio" name="theme" checked={theme === v} onChange={() => setTheme(v)} /> {label}
          </label>
        ))}
      </fieldset>
      {s.enabled && (
        <div className="flex flex-col gap-2">
          <p className="font-cond text-xs uppercase tracking-wide text-ink-2">{t("settings.account")}</p>
          <p>{s.email}</p>
          <div className="flex gap-2">
            <Button onClick={() => s.email && requestPasswordReset(s.email)
              .then(() => toast(t("settings.password.sent")), e => toast((e as Error).message, "error"))}>{t("settings.password")}</Button>
            <Button variant="ghost" onClick={() => s.signOut()}>{t("settings.signout")}</Button>
          </div>
        </div>
      )}
    </section>
  );
}
```

`frontend/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import { Providers } from "./app/providers";
import { routes } from "./app/router";
import "./design/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Providers><RouterProvider router={createBrowserRouter(routes)} /></Providers>
  </StrictMode>,
);
```

(`App.tsx` и `styles.css` больше не подключаются; они удаляются в Task 9.)

- [ ] **Step 6: Тест на истёкшую сессию (Review Focus 5)**

Дописать в `frontend/src/app/router.test.tsx`:

```tsx
import { Unauthorized } from "../lib/api";
import { toLogin } from "../lib/queries";

it("a 401 anywhere sends the user to login and back", () => {
  const assign = vi.fn();
  vi.stubGlobal("location", { ...location, pathname: "/app/checks/" + "c".repeat(32), search: "", assign });
  toLogin(new Unauthorized("x"));
  expect(assign).toHaveBeenCalledWith("/login?next=" + encodeURIComponent("/app/checks/" + "c".repeat(32)));
  toLogin(new Error("not auth"));
  expect(assign).toHaveBeenCalledTimes(1);
  vi.unstubAllGlobals();
});
```

- [ ] **Step 7: Запустить тесты — должны пройти**

Run: `npm --prefix frontend test -- src/app && npx --prefix frontend tsc -b frontend`
Expected: PASS (4 теста). Проекты `ChecksPage`, `NewCheckPage`, `ReportPage` создаются в Task 5–7; до этого создать файлы-заглушки с `export default function X() { return null; }`, чтобы ленивые импорты разрешались, и заменить их в своих задачах.

- [ ] **Step 8: Commit**

```bash
git add frontend
git commit -m "Маршруты, оболочка с боковым меню, вход и настройки; 401 ведёт на вход и обратно"
```

---

### Task 5: Мои проверки

**Files:**
- Create: `frontend/src/platform/checks/ChecksPage.tsx`, `frontend/src/platform/checks/ChecksTable.tsx`
- Test: `frontend/src/platform/checks/checks.test.tsx`

**Interfaces:**
- Consumes: `useChecks`, `useRenameCheck` (lib/queries), `CheckRow` (lib/types), `SectionChip`, `Badge`, `EmptyState`, `Button`, `Dialog` (design), `t` (lib/i18n), `SECTIONS` (lib/labels).
- Produces: `<ChecksTable rows: CheckRow[] onRename(id: string, title: string): void />` — строки — ссылки на `/app/checks/:id`.

- [ ] **Step 1: Написать падающие тесты**

`frontend/src/platform/checks/checks.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import type { CheckRow } from "../../lib/types";
import ChecksTable from "./ChecksTable";

const row = (over: Partial<CheckRow> = {}): CheckRow => ({
  id: "a".repeat(32), title: "ЖК «Алатау», блок 2", status: "done", created_at: "2026-10-11T08:00:00+00:00",
  sections: ["PZ", "AR", "KR", "SMETA"], summary: { MISMATCH: 3, MISSING: 1, MATCH: 4 }, reviewed: 2,
  expires_at: "2026-10-18T08:00:00+00:00", ...over,
});
const show = (rows: CheckRow[], onRename = vi.fn()) =>
  render(<MemoryRouter><ChecksTable rows={rows} onRename={onRename} /></MemoryRouter>);

describe("checks table", () => {
  it("shows result, expert progress and missing sections", () => {
    show([row({ sections: ["PZ"] })]);
    const r = screen.getByRole("row", { name: /Алатау/ });
    expect(within(r).getByText("3 ≠")).toBeInTheDocument();
    expect(within(r).getByText("1 нет")).toBeInTheDocument();
    expect(within(r).getByText("2/4")).toBeInTheDocument();
    expect(within(r).getByText("АР")).toHaveAttribute("data-present", "false");
    expect(within(r).getByRole("link", { name: /Алатау/ })).toHaveAttribute("href", "/app/checks/" + "a".repeat(32));
  });

  it("shows status instead of a result while running or failed", () => {
    show([row({ id: "b".repeat(32), title: "Школа", status: "pending", summary: null }), row({ id: "c".repeat(32), title: "Котельная", status: "error", summary: null })]);
    expect(screen.getByText("идёт проверка…")).toBeInTheDocument();
    expect(screen.getByText("ошибка")).toBeInTheDocument();
  });

  it("long titles are cut with the full text in the tooltip", () => {  // Review Focus 3
    const long = "Көпқабатты тұрғын үй кешені ".repeat(8).trim();
    show([row({ title: long })]);
    const link = screen.getByRole("link", { name: long });
    expect(link).toHaveAttribute("title", long);
    expect(link.className).toMatch(/truncate/);
  });

  it("rename sends the new title", async () => {
    const onRename = vi.fn();
    show([row()], onRename);
    await userEvent.click(screen.getByRole("button", { name: "Переименовать" }));
    const input = screen.getByRole("textbox", { name: "Название" });
    await userEvent.clear(input);
    await userEvent.type(input, "Блок 2{Enter}");
    expect(onRename).toHaveBeenCalledWith("a".repeat(32), "Блок 2");
  });
});
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `npm --prefix frontend test -- src/platform/checks`
Expected: FAIL — `ChecksTable` не найден (или заглушка ничего не рисует).

- [ ] **Step 3: Реализация**

`frontend/src/platform/checks/ChecksTable.tsx`:

```tsx
import { useState } from "react";
import { Link } from "react-router";
import Button from "../../design/Button";
import Dialog from "../../design/Dialog";
import SectionChip from "../../design/SectionChip";
import { t, type Key } from "../../lib/i18n";
import { SECTIONS } from "../../lib/labels";
import type { CheckRow } from "../../lib/types";

const date = (iso: string) => new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });

function Result({ r }: { r: CheckRow }) {
  if (r.status !== "done" || !r.summary) return <span className="text-ink-2">{t(`checks.status.${r.status}` as Key)}</span>;
  const { MISMATCH, MISSING } = r.summary;
  if (!MISMATCH && !MISSING) return <span className="text-green">всё сходится</span>;
  return (
    <span className="num">
      {MISMATCH > 0 && <span className="text-pencil font-semibold">{MISMATCH} ≠</span>}
      {MISMATCH > 0 && MISSING > 0 && " · "}
      {MISSING > 0 && <span className="text-amber">{MISSING} нет</span>}
    </span>
  );
}

export default function ChecksTable({ rows, onRename }: { rows: CheckRow[]; onRename: (id: string, title: string) => void }) {
  const [editing, setEditing] = useState<CheckRow | null>(null);
  const [title, setTitle] = useState("");
  const save = () => { if (editing && title.trim()) onRename(editing.id, title.trim()); setEditing(null); };

  return (
    <>
      <table className="w-full table-fixed border-collapse bg-sheet border border-line text-sm">
        <thead>
          <tr className="text-left font-cond text-[11px] uppercase tracking-wide text-ink-2">
            <th className="p-2 w-[38%]">{t("checks.col.title")}</th><th className="p-2">{t("checks.col.sections")}</th>
            <th className="p-2">{t("checks.col.result")}</th><th className="p-2 w-20">{t("checks.col.expert")}</th>
            <th className="p-2 w-20">{t("checks.col.date")}</th><th className="p-2 w-24">{t("checks.col.expires")}</th><th className="w-10" />
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const toReview = r.summary ? r.summary.MISMATCH + r.summary.MISSING : 0;
            return (
              <tr key={r.id} aria-label={r.title} className="border-t border-line hover:bg-paper">
                <td className="p-2 min-w-0">
                  <Link to={`/app/checks/${r.id}`} title={r.title} className="block truncate font-semibold text-ink hover:text-blue">{r.title}</Link>
                </td>
                <td className="p-2"><span className="flex gap-1">{SECTIONS.map(s => <SectionChip key={s} section={s} present={r.sections.includes(s)} />)}</span></td>
                <td className="p-2"><Result r={r} /></td>
                <td className="p-2 num">{r.status === "done" && toReview ? `${r.reviewed}/${toReview}` : "—"}</td>
                <td className="p-2">{date(r.created_at)}</td>
                <td className="p-2 text-ink-2">{date(r.expires_at)}</td>
                <td className="p-1">
                  <Button size="sm" variant="ghost" aria-label={t("checks.rename")} title={t("checks.rename")}
                    onClick={() => { setEditing(r); setTitle(r.title); }}>✎</Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <Dialog open={editing !== null} onOpenChange={o => !o && setEditing(null)} title={t("checks.rename")}>
        <form className="p-4 flex flex-col gap-3" onSubmit={e => { e.preventDefault(); save(); }}>
          <input aria-label="Название" maxLength={200} value={title} onChange={e => setTitle(e.target.value)} autoFocus
            className="min-h-9 border border-control rounded px-2.5 bg-sheet" />
          <Button type="submit" variant="primary" className="self-start">{t("checks.rename.save")}</Button>
        </form>
      </Dialog>
    </>
  );
}
```

`frontend/src/platform/checks/ChecksPage.tsx`:

```tsx
import { Link } from "react-router";
import Button from "../../design/Button";
import EmptyState from "../../design/EmptyState";
import { useToast } from "../../design/Toast";
import { t } from "../../lib/i18n";
import { useChecks, useRenameCheck } from "../../lib/queries";
import ChecksTable from "./ChecksTable";

export default function ChecksPage() {
  const checks = useChecks();
  const rename = useRenameCheck();
  const toast = useToast();
  if (checks.isPending) return <p className="p-6 text-ink-2">Загрузка…</p>;
  if (checks.isError) return <EmptyState title="Список не загрузился">{(checks.error as Error).message}</EmptyState>;
  const rows = checks.data;
  return (
    <section className="p-6 flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold flex-1">{t("checks.count", { n: rows.length })}</h1>
        <Link to="/app/new"><Button variant="primary">+ {t("nav.new")}</Button></Link>
      </div>
      {rows.length === 0
        ? <EmptyState title={t("checks.empty")} action={<a href="/demo" className="text-blue underline">{t("nav.demo")}</a>}>{t("checks.empty.body")}</EmptyState>
        : <ChecksTable rows={rows} onRename={(id, title) => rename.mutate({ id, title }, { onError: e => toast((e as Error).message, "error") })} />}
    </section>
  );
}
```

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `npm --prefix frontend test -- src/platform/checks`
Expected: PASS (4 теста).

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "Мои проверки: таблица с итогом, разделами, прогрессом эксперта и переименованием"
```

---

### Task 6: Мастер новой проверки

**Files:**
- Create: `frontend/src/platform/new/NewCheckPage.tsx`, `frontend/src/platform/new/Stepper.tsx`
- Move: `frontend/src/components/FileReview.tsx` → `frontend/src/platform/report/FileReview.tsx`
- Test: `frontend/src/platform/new/new.test.tsx`

**Interfaces:**
- Consumes: `uploadFiles(files, onProgress)`, `startUploaded(id, choices)`, `getCheck(id)` (lib/api); `FileReview` (props `{ files, busy, status, onStart, onCancel }`); `queryClient`.
- Produces:
  - `type WizardState = { step: "files" } | { step: "uploading"; sent: number; total: number } | { step: "sections"; id: string; files: Record<string, UploadedFile> } | { step: "running"; id: string } | { step: "failed"; message: string }`
  - `reduceWizard(s: WizardState, e: WizardEvent): WizardState`, `WizardEvent = { type: "upload"; total: number } | { type: "progress"; sent: number } | { type: "uploaded"; id: string; files: Record<string, UploadedFile> } | { type: "start" } | { type: "fail"; message: string } | { type: "reset" }`
  - После старта — переход на `/app/checks/:id` (там опрос до готовности).
  - `/app/new?id=<id>` (незавершённый шаг «Разделы») — загружает `getCheck(id)` и, если `status === "uploaded"`, открывает шаг «Разделы».

- [ ] **Step 1: Написать падающие тесты**

`frontend/src/platform/new/new.test.tsx`:

```ts
import { describe, expect, it } from "vitest";
import { reduceWizard, type WizardState } from "./NewCheckPage";

describe("new check wizard", () => {
  it("goes files → uploading → sections → running", () => {
    let s: WizardState = { step: "files" };
    s = reduceWizard(s, { type: "upload", total: 10 });
    expect(s).toEqual({ step: "uploading", sent: 0, total: 10 });
    s = reduceWizard(s, { type: "progress", sent: 4 });
    expect(s).toEqual({ step: "uploading", sent: 4, total: 10 });
    s = reduceWizard(s, { type: "uploaded", id: "x", files: {} });
    expect(s.step).toBe("sections");
    s = reduceWizard(s, { type: "start" });
    expect(s).toEqual({ step: "running", id: "x" });
  });

  it("progress outside uploading and start outside sections are ignored", () => {
    const files: WizardState = { step: "files" };
    expect(reduceWizard(files, { type: "progress", sent: 3 })).toBe(files);
    expect(reduceWizard(files, { type: "start" })).toBe(files);
  });

  it("a failure is shown and reset returns to files", () => {
    const s = reduceWizard({ step: "uploading", sent: 1, total: 2 }, { type: "fail", message: "сеть" });
    expect(s).toEqual({ step: "failed", message: "сеть" });
    expect(reduceWizard(s, { type: "reset" })).toEqual({ step: "files" });
  });
});
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `npm --prefix frontend test -- src/platform/new`
Expected: FAIL — `reduceWizard` не экспортирован.

- [ ] **Step 3: Реализация**

```bash
git mv frontend/src/components/FileReview.tsx frontend/src/platform/report/FileReview.tsx
```

В `FileReview.tsx`: импорты `"../labels"`, `"../types"` → `"../../lib/labels"`, `"../../lib/types"`; корневой `<section className="intake file-review">` → `<section className="max-w-3xl flex flex-col gap-3">`; таблицу → `className="w-full bg-sheet border border-line text-sm"`; `<select>` → `className="min-h-[26px] border border-control rounded px-1.5 bg-sheet"`; `.note` → `className="border-l-[3px] border-amber bg-amber-wash px-3 py-2 text-sm"`; кнопки → `Button` из `../../design/Button` (`variant="primary"` для «Проверить»); заголовок `h1` оставить, но сделать `text-xl font-semibold`.

`frontend/src/platform/new/Stepper.tsx`:

```tsx
import { t } from "../../lib/i18n";

const STEPS = ["new.step.files", "new.step.sections", "new.step.run"] as const;

export default function Stepper({ current }: { current: 0 | 1 | 2 }) {
  return (
    <ol className="flex gap-2" aria-label="Шаги">
      {STEPS.map((k, i) => (
        <li key={k} aria-current={i === current ? "step" : undefined}
          className={"flex-1 border-t-[3px] pt-1 text-sm " + (i < current ? "border-green text-green" : i === current ? "border-blue text-blue font-semibold" : "border-line text-ink-2")}>
          {i + 1} · {t(k)}
        </li>
      ))}
    </ol>
  );
}
```

`frontend/src/platform/new/NewCheckPage.tsx`:

```tsx
import { useEffect, useReducer, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router";
import Button from "../../design/Button";
import { getCheck, startUploaded, uploadFiles } from "../../lib/api";
import { t } from "../../lib/i18n";
import type { UploadedFile } from "../../lib/types";
import FileReview from "../report/FileReview";
import Stepper from "./Stepper";

export type WizardState =
  | { step: "files" }
  | { step: "uploading"; sent: number; total: number }
  | { step: "sections"; id: string; files: Record<string, UploadedFile> }
  | { step: "running"; id: string }
  | { step: "failed"; message: string };
export type WizardEvent =
  | { type: "upload"; total: number } | { type: "progress"; sent: number }
  | { type: "uploaded"; id: string; files: Record<string, UploadedFile> }
  | { type: "start" } | { type: "fail"; message: string } | { type: "reset" };

export function reduceWizard(s: WizardState, e: WizardEvent): WizardState {
  switch (e.type) {
    case "upload": return { step: "uploading", sent: 0, total: e.total };
    case "progress": return s.step === "uploading" ? { ...s, sent: e.sent } : s;
    case "uploaded": return { step: "sections", id: e.id, files: e.files };
    case "start": return s.step === "sections" ? { step: "running", id: s.id } : s;
    case "fail": return { step: "failed", message: e.message };
    case "reset": return { step: "files" };
  }
}

const mb = (b: number) => (b / 2 ** 20).toLocaleString("ru-RU", { maximumFractionDigits: 1 });

export default function NewCheckPage() {
  const [s, dispatch] = useReducer(reduceWizard, { step: "files" });
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {  // a link to an unfinished wizard resumes at "sections"
    const id = params.get("id");
    if (!id) return;
    getCheck(id).then(c => c.status === "uploaded"
      ? dispatch({ type: "uploaded", id, files: c.files })
      : nav(`/app/checks/${id}`, { replace: true }), e => dispatch({ type: "fail", message: (e as Error).message }));
  }, []);

  const upload = async (files: FileList) => {
    if (!files.length) return;
    dispatch({ type: "upload", total: [...files].reduce((n, f) => n + f.size, 0) });
    try {
      const r = await uploadFiles(files, sent => dispatch({ type: "progress", sent }));
      setParams({ id: r.id }, { replace: true });
      dispatch({ type: "uploaded", id: r.id, files: r.files });
    } catch (e) { dispatch({ type: "fail", message: (e as Error).message }); }
  };

  const current = s.step === "sections" ? 1 : s.step === "running" ? 2 : 0;
  return (
    <section className="p-6 flex flex-col gap-5 max-w-4xl">
      <h1 className="text-2xl font-semibold">{t("nav.new")}</h1>
      <Stepper current={current} />
      {(s.step === "files" || s.step === "failed") && (
        <label className="block border-2 border-dashed border-control bg-sheet p-10 text-center cursor-pointer"
          onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); upload(e.dataTransfer.files); }}>
          <span className="block font-semibold">{t("new.drop")}</span>
          <span className="text-sm text-ink-2">{t("new.drop.hint")}</span>
          <input ref={input} type="file" multiple accept=".pdf,.docx" className="sr-only" onChange={e => e.target.files && upload(e.target.files)} />
        </label>
      )}
      {s.step === "failed" && <p role="alert" className="text-pencil">{s.message}</p>}
      {s.step === "uploading" && (
        <div role="status" className="flex flex-col gap-2">
          <p>{t("new.uploading", { sent: mb(s.sent), total: mb(s.total) })}</p>
          <div className="h-1.5 bg-line"><div className="h-1.5 bg-blue" style={{ width: `${s.total ? (100 * s.sent) / s.total : 0}%` }} /></div>
        </div>
      )}
      {s.step === "sections" && (
        <FileReview files={s.files} busy={false} status={null} onCancel={() => { setParams({}); dispatch({ type: "reset" }); }}
          onStart={async choices => {
            dispatch({ type: "start" });
            try { await startUploaded(s.id, choices); nav(`/app/checks/${s.id}`); }
            catch (e) { dispatch({ type: "fail", message: (e as Error).message }); }
          }} />
      )}
      {s.step === "running" && <p role="status">{t("new.running")}</p>}
      {s.step === "failed" && <Button onClick={() => dispatch({ type: "reset" })}>Начать заново</Button>}
    </section>
  );
}
```

(`uploadFiles` вызывает `onProgress(sent, total)`; здесь используется только `sent`.)

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `npm --prefix frontend test -- src/platform/new && npx --prefix frontend tsc -b frontend`
Expected: PASS (3 теста).

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "Мастер новой проверки: файлы → разделы → проверка, возврат к незавершённому шагу"
```

---

### Task 7: Отчёт в три колонки

**Files:**
- Create: `frontend/src/platform/report/ReportPage.tsx`, `frontend/src/platform/report/FindingsColumn.tsx`, `frontend/src/platform/report/FindingDetail.tsx`, `frontend/src/platform/report/useReportKeys.ts`, `frontend/src/platform/report/findings.ts`
- Move: `components/Viewer.tsx` → `platform/report/DocumentPane.tsx`, `components/RefPane.tsx` → `platform/report/RefPane.tsx`, `components/TepTables.tsx` → `platform/report/TepTab.tsx`, `components/Completeness.tsx` → `platform/report/CompletenessTab.tsx`, `components/ReviewBar.tsx` → `platform/report/ReviewBar.tsx`
- Modify: `frontend/src/lib/export.ts` (импорты `comparedLabel`, `EXPERT` из новых мест)
- Test: `frontend/src/platform/report/report.test.tsx`

**Interfaces:**
- Consumes: `useCheck(id)` (lib/queries), `saveReview` (lib/api), `createReviewQueue` (lib/reviewQueue), `exportXlsx(report, reviews, checkId)` (lib/export), `DocumentPane` (props `{ checkId, report, selection, top? }`), `StampSummary`, `Badge`, `SectionChip`, `Kbd`.
- Produces:
  - `findings.ts`: `comparedLabel(f)`, `Filter`, `NO_FILTER`, `applyFilter(list, filter, reviewOf)` — перенос без изменений из `components/Findings.tsx`.
  - `<FindingsColumn report filter onFilter current onPick reviewOf bad ok />` — вкладки, фильтры, список.
  - `<FindingDetail finding: Finding | null; review: Review; onReview(r: Review): void; saving: boolean />` — значения по разделам, Δ % (только при `refs.length === 2` и `delta_rel` ≠ null), вердикт, комментарий, примечания.
  - `useReportKeys({ list, current, pick, toggleVerdict, enabled })` — `j`/`k` (`о`/`л`), `1`/`2`; `←`/`→`, `s` остаются в `DocumentPane`.

- [ ] **Step 1: Перенести файлы и логику фильтров**

```bash
cd frontend/src
git mv components/Viewer.tsx platform/report/DocumentPane.tsx
git mv components/RefPane.tsx platform/report/RefPane.tsx
git mv components/TepTables.tsx platform/report/TepTab.tsx
git mv components/Completeness.tsx platform/report/CompletenessTab.tsx
git mv components/ReviewBar.tsx platform/report/ReviewBar.tsx
cd ../..
```

`frontend/src/platform/report/findings.ts` — скопировать из `components/Findings.tsx` функцию `comparedLabel`, интерфейс `Filter`, `NO_FILTER`, `applyFilter` (тела без изменений), с импортами `import { SECTION, TYPE } from "../../lib/labels"; import type { Finding, Review } from "../../lib/types";`. В перенесённых файлах исправить импорты на `../../lib/...` и `./...`. В `lib/export.ts`: `import { comparedLabel } from "../platform/report/findings"; import { EXPERT } from "../platform/report/ReviewBar";`.

Классы старого CSS в перенесённых компонентах заменить на Tailwind: `.viewer-head` → `flex items-center gap-2 px-3 py-2 border-b border-line`, `.evidence` → `px-3 py-2 text-sm text-ink-2 border-b border-line`, `mark` внутри — `className="bg-transparent text-pencil font-semibold"`, `.canvas-wrap` → `relative flex-1 overflow-auto p-4 bg-doc`, `.page` → `relative mx-auto w-fit bg-white shadow-[0_0_0_1px_var(--line)]`, `.page-bar` → `flex items-center gap-1.5 px-3 py-1 border-b border-line text-sm text-ink-2`, кнопки листания/масштаба — `Button size="sm"`, `.panes` → `flex-1 grid min-h-0` + `grid-cols-2` в режиме «рядом», `.pane` → `flex flex-col min-h-0 min-w-0`, `.refs button[aria-pressed=true]` → `Button size="sm" variant={pressed ? "primary" : "secondary"}`. Обводка — класс `pencil-ring` (уже в `design/index.css`).

- [ ] **Step 2: Написать падающие тесты**

`frontend/src/platform/report/report.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Finding, Review } from "../../lib/types";
import FindingDetail from "./FindingDetail";
import { reportState } from "./ReportPage";

const f = (over: Partial<Finding> = {}): Finding => ({
  type: "AREA_PZ_VS_AR_EXPLICATION", field: "total_area_m2", verdict: "MISMATCH", notes: ["экспликация без лестничных клеток"],
  refs: [{ section: "PZ", value: 1247.79, page: 1 }, { section: "AR", value: 1382, page: 2 }], delta_rel: -0.097, ...over,
});
const none: Review = { verdict: null, comment: "" };

describe("finding detail", () => {
  it("shows both values, the difference and the notes", () => {
    render(<FindingDetail finding={f()} review={none} onReview={vi.fn()} saving={false} />);
    // ru-RU numbers use a no-break space between thousands: match any space
    expect(screen.getByText(/^1\s247,79$/)).toBeInTheDocument();
    expect(screen.getByText(/^1\s382$/)).toBeInTheDocument();
    expect(screen.getByText("−9,7 %")).toBeInTheDocument();
    expect(screen.getByText("экспликация без лестничных клеток")).toBeInTheDocument();
  });

  it("one place or three places: every value, no difference row (Review Focus 1)", () => {
    const three = f({ refs: [{ section: "PZ", value: 10, page: 1 }, { section: "PZ", value: 12, page: 2 }, { section: "PZ", value: 11, page: 3 }], delta_rel: null });
    render(<FindingDetail finding={three} review={none} onReview={vi.fn()} saving={false} />);
    expect(screen.getAllByRole("row")).toHaveLength(3);
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it("nothing selected: an empty state (Review Focus 4)", () => {
    render(<FindingDetail finding={null} review={none} onReview={vi.fn()} saving={false} />);
    expect(screen.getByText("Выберите замечание слева")).toBeInTheDocument();
  });

  it("verdict buttons send the review", () => {
    const onReview = vi.fn();
    render(<FindingDetail finding={f()} review={none} onReview={onReview} saving={false} />);
    screen.getByRole("button", { name: /Подтверждаю/ }).click();
    expect(onReview).toHaveBeenCalledWith({ verdict: "confirmed", comment: "" });
  });
});

describe("report page state (Review Focus 2)", () => {
  it("maps every status to something the user can read", () => {
    expect(reportState(undefined, null)).toEqual({ kind: "loading" });
    expect(reportState({ id: "x", status: "pending" }, null)).toEqual({ kind: "message", text: "Идёт проверка документов…" });
    expect(reportState({ id: "x", status: "receiving" }, null).kind).toBe("message");
    expect(reportState({ id: "x", status: "error", error: "boom" }, null)).toEqual({ kind: "message", text: "Проверка не выполнена: boom", error: true });
    expect(reportState({ id: "x", status: "uploaded", files: {} }, null)).toEqual({ kind: "redirect", to: "/app/new?id=x" });
    expect(reportState(undefined, new Error("Проверка не найдена"))).toEqual({ kind: "message", text: "Проверка не найдена или удалена.", error: true });
  });
});
```

- [ ] **Step 3: Запустить — убедиться, что падают**

Run: `npm --prefix frontend test -- src/platform/report`
Expected: FAIL — `FindingDetail`, `reportState` не найдены.

- [ ] **Step 4: Панель замечания**

`frontend/src/platform/report/FindingDetail.tsx`:

```tsx
import { useEffect, useState } from "react";
import Badge from "../../design/Badge";
import Button from "../../design/Button";
import EmptyState from "../../design/EmptyState";
import Kbd from "../../design/Kbd";
import { t } from "../../lib/i18n";
import { SECTION, VERDICT, fieldName, fmt } from "../../lib/labels";
import type { ExpertVerdict, Finding, Review } from "../../lib/types";
import { comparedLabel } from "./findings";

const KIND = { MISMATCH: "mismatch", MISSING: "missing", MATCH: "match" } as const;
const pct = (d: number) => `${d < 0 ? "−" : "+"}${Math.abs(d * 100).toFixed(1).replace(".", ",")} %`;

interface Props { finding: Finding | null; review: Review; onReview: (r: Review) => void; saving: boolean }

export default function FindingDetail({ finding, review, onReview, saving }: Props) {
  const [comment, setComment] = useState(review.comment);
  useEffect(() => setComment(review.comment), [review.comment, finding]);
  if (!finding) return <EmptyState title={t("report.detail.empty")} />;

  const toggle = (v: ExpertVerdict) => onReview({ verdict: review.verdict === v ? null : v, comment });
  const saveComment = () => { if (comment.trim() !== review.comment) onReview({ ...review, comment: comment.trim() }); };
  const pair = finding.refs.length === 2 && finding.delta_rel != null;

  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap gap-1"><Badge kind={KIND[finding.verdict]}>{VERDICT[finding.verdict]}</Badge>
        {finding.needs_expert && <Badge kind="expert">эксперту</Badge>}{finding.low_confidence && <Badge kind="scan">скан</Badge>}</div>
      <h2 className="text-lg font-semibold leading-snug">{fieldName(finding.field)}</h2>
      <p className="text-sm text-ink-2">{finding.object_name ? `${finding.object_name} · ` : ""}{comparedLabel(finding)}</p>
      <table className="w-full text-sm border border-line">
        <tbody>
          {finding.refs.map((r, i) => (
            <tr key={i} className="border-t border-line first:border-t-0">
              <td className="p-1.5 font-cond">{r.label ?? SECTION[r.section]}</td>
              <td className={"p-1.5 num text-right " + (r.value == null ? "text-amber" : "")}>{fmt(r.value)}</td>
              <td className="p-1.5 text-ink-2">{r.page ? `стр. ${r.page}` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {pair && <p className="num text-pencil font-semibold">{pct(finding.delta_rel!)}</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant={review.verdict === "confirmed" ? "primary" : "secondary"} onClick={() => toggle("confirmed")}>
          {t("verdict.confirm")} <Kbd>1</Kbd></Button>
        <Button variant={review.verdict === "false_positive" ? "primary" : "secondary"} onClick={() => toggle("false_positive")}>
          {t("verdict.false")} <Kbd>2</Kbd></Button>
        {saving && <span role="status" className="text-xs text-ink-2 self-center">сохраняем…</span>}
      </div>
      <textarea aria-label={t("verdict.comment")} placeholder={t("verdict.comment")} maxLength={2000} rows={3}
        value={comment} onChange={e => setComment(e.target.value)} onBlur={saveComment}
        className="border border-control rounded px-2.5 py-1.5 bg-sheet text-sm" />
      {finding.notes.length > 0 && (
        <ul className="text-sm text-ink-2 list-disc pl-4">{finding.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Клавиши, левая колонка, страница**

`frontend/src/platform/report/useReportKeys.ts`:

```ts
import { useEffect } from "react";
import type { ExpertVerdict, Finding } from "../../lib/types";

const typing = (t: EventTarget | null) => t instanceof HTMLElement && /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName);

/** j/k (о/л on the Russian layout) walk the visible findings, 1/2 set the verdict of the open one. */
export function useReportKeys(o: {
  list: Finding[]; current: Finding | null; pick: (f: Finding) => void;
  toggleVerdict: (f: Finding, v: ExpertVerdict) => void; enabled: boolean;
}) {
  useEffect(() => {
    if (!o.enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      if ((e.key === "1" || e.key === "2") && o.current) {
        e.preventDefault();
        o.toggleVerdict(o.current, e.key === "1" ? "confirmed" : "false_positive");
        return;
      }
      const step = e.key === "j" || e.key === "о" ? 1 : e.key === "k" || e.key === "л" ? -1 : 0;
      if (!step || !o.list.length) return;
      e.preventDefault();
      const i = o.current ? o.list.indexOf(o.current) : -1;
      o.pick(o.list[i < 0 ? 0 : Math.min(o.list.length - 1, Math.max(0, i + step))]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
}
```

`frontend/src/platform/report/FindingsColumn.tsx` — перенести из `components/Findings.tsx` компоненты `Values`, `Remark`, `FilterBar` и default-компонент `Findings` (переименовав его в `FindingsColumn`), с вкладками из `ReportView` («Замечания», «ТЭП», «Комплектность»: `TepTab`, `CompletenessTab`). Пропсы: `{ report, bad, ok, filter, onFilter, matchesOpen, onMatchesOpen, current, onPick, reviewOf, onPickRefs(refs: Ref[]) }`. Классы: строки замечаний — `w-full text-left grid grid-cols-[28px_1fr] gap-x-2 px-3 py-2.5 border-b border-line hover:bg-paper`; активная — `aria-current="true"` + `shadow-[inset_3px_0_0_var(--pencil)] bg-pencil-wash`; значения — `num font-semibold`, знак `≠` — `text-pencil px-1.5`; плашки — `Badge`; фильтры — `select` с `min-h-[26px] border border-control rounded px-1.5 bg-sheet text-[13px]`; пустой список — `t("report.none")`.

`frontend/src/platform/report/ReportPage.tsx`:

```tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useParams } from "react-router";
import Button from "../../design/Button";
import EmptyState from "../../design/EmptyState";
import SectionChip from "../../design/SectionChip";
import StampSummary from "../../design/StampSummary";
import { useToast } from "../../design/Toast";
import { saveReview, Unauthorized } from "../../lib/api";
import { exportXlsx } from "../../lib/export";
import { t } from "../../lib/i18n";
import { SECTIONS } from "../../lib/labels";
import { toLogin, useCheck } from "../../lib/queries";
import { createReviewQueue } from "../../lib/reviewQueue";
import type { CheckStatus, ExpertVerdict, Finding, Ref, Report, Review, Reviews } from "../../lib/types";
import DocumentPane from "./DocumentPane";
import FindingDetail from "./FindingDetail";
import FindingsColumn from "./FindingsColumn";
import { NO_FILTER, applyFilter, type Filter } from "./findings";
import { useReportKeys } from "./useReportKeys";

export type ReportState =
  | { kind: "loading" } | { kind: "redirect"; to: string }
  | { kind: "message"; text: string; error?: boolean } | { kind: "report"; data: Extract<CheckStatus, { status: "done" }> };

export function reportState(data: CheckStatus | undefined, error: unknown): ReportState {
  if (error) return { kind: "message", text: t("report.missing"), error: true };
  if (!data) return { kind: "loading" };
  switch (data.status) {
    case "pending": return { kind: "message", text: t("report.pending") };
    case "receiving": return { kind: "message", text: t("report.receiving") };
    case "uploaded": return { kind: "redirect", to: `/app/new?id=${data.id}` };
    case "error": return { kind: "message", text: t("report.error", { error: data.error }), error: true };
    case "done": return { kind: "report", data };
  }
}

const EMPTY: Review = { verdict: null, comment: "" };

export default function ReportPage() {
  const { id = "" } = useParams();
  const q = useCheck(id);
  const state = reportState(q.data, q.error);
  if (state.kind === "loading") return <p className="p-6 text-ink-2">Загрузка…</p>;
  if (state.kind === "redirect") return <Navigate to={state.to} replace />;
  if (state.kind === "message") return <EmptyState title={state.text} />;
  return <ReportBody checkId={id} report={state.data.report} title={state.data.title ?? ""} initial={state.data.reviews ?? {}} />;
}

function ReportBody({ checkId, report, title, initial }: { checkId: string; report: Report; title: string; initial: Reviews }) {
  const toast = useToast();
  const [reviews, setReviews] = useState<Reviews>(initial);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState<Filter>(NO_FILTER);
  const [matchesOpen, setMatchesOpen] = useState(false);
  const queue = useRef(createReviewQueue((n, r) => saveReview(checkId, n, r)));
  const reviewOf = useCallback((f: Finding) => reviews[String(report.findings.indexOf(f))], [reviews, report]);
  const allBad = useMemo(() => report.findings.filter(f => f.verdict !== "MATCH"), [report]);
  const bad = useMemo(() => applyFilter(allBad, filter, reviewOf), [allBad, filter, reviewOf]);
  const ok = useMemo(() => applyFilter(report.findings.filter(f => f.verdict === "MATCH"), filter, reviewOf), [report, filter, reviewOf]);
  const [current, setCurrent] = useState<Finding | null>(bad[0] ?? null);
  const [selection, setSelection] = useState<{ refs: Ref[]; finding?: Finding } | null>(current ? { refs: current.refs, finding: current } : null);

  const pick = (f: Finding) => { setCurrent(f); setSelection({ refs: f.refs, finding: f }); if (ok.includes(f)) setMatchesOpen(true); };
  useEffect(() => { if (current && !bad.includes(current) && !ok.includes(current) && bad[0]) pick(bad[0]); }, [filter]);

  const review = (f: Finding, next: Review) => {
    const key = String(report.findings.indexOf(f));
    const prev = reviews[key];
    setReviews(r => { const { [key]: _, ...rest } = r; return next.verdict || next.comment ? { ...rest, [key]: next } : rest; });
    setSaving(true);
    queue.current.push(Number(key), next).catch(e => {
      if (e instanceof Unauthorized) { toLogin(e); return; }
      setReviews(r => { const { [key]: _, ...rest } = r; return prev ? { ...rest, [key]: prev } : rest; });
      toast((e as Error).message, "error");
    }).finally(() => setSaving(false));
  };
  const toggleVerdict = (f: Finding, v: ExpertVerdict) => {
    const r = reviewOf(f) ?? EMPTY;
    review(f, { ...r, verdict: r.verdict === v ? null : v });
  };
  useReportKeys({ list: matchesOpen ? [...bad, ...ok] : bad, current, pick, toggleVerdict, enabled: true });

  const s = report.summary, c = report.completeness;
  const reviewed = allBad.filter(f => reviewOf(f)?.verdict).length;
  return (
    <div className="flex flex-col h-full">
      <header className="flex flex-wrap items-center gap-3 px-4 py-2 bg-sheet border-b border-line">
        <h1 className="text-lg font-semibold truncate max-w-[40%]" title={title}>{title}</h1>
        <span className="flex gap-1">{SECTIONS.map(x => <SectionChip key={x} section={x} present={c.present.includes(x)} />)}</span>
        <span className="flex-1" />
        <Button size="sm" onClick={() => exportXlsx(report, reviews, checkId).catch(e => toast((e as Error).message, "error"))}>{t("report.export")}</Button>
      </header>
      <div className="px-4 py-2"><StampSummary items={[
        { label: "Разделы", value: `${c.present.length}/${c.required.length}`, tone: c.missing.length ? "bad" : "ok" },
        { label: "Расхождения", value: String(s.MISMATCH), tone: s.MISMATCH ? "bad" : "ok" },
        { label: "Нет значения", value: String(s.MISSING), tone: s.MISSING ? "warn" : "ok" },
        { label: "Совпало", value: String(s.MATCH) },
        { label: "Эксперт", value: `${reviewed}/${allBad.length}`, tone: allBad.length && reviewed === allBad.length ? "ok" : undefined },
      ]} /></div>
      <div className="flex-1 min-h-0 grid grid-cols-[minmax(280px,30%)_1fr_minmax(260px,24%)] border-t border-line">
        <aside className="min-h-0 overflow-auto bg-sheet border-r border-line">
          <FindingsColumn report={report} bad={bad} ok={ok} filter={filter} onFilter={setFilter} matchesOpen={matchesOpen}
            onMatchesOpen={setMatchesOpen} current={current} onPick={pick} reviewOf={reviewOf}
            onPickRefs={refs => setSelection({ refs })} />
        </aside>
        <DocumentPane checkId={checkId} report={report} selection={selection} />
        <aside className="min-h-0 overflow-auto bg-sheet border-l border-line">
          <FindingDetail finding={current} review={(current && reviewOf(current)) ?? EMPTY} saving={saving}
            onReview={r => current && review(current, r)} />
        </aside>
      </div>
    </div>
  );
}
```

(`DocumentPane` больше не получает `top` с панелью вердикта — вердикт теперь в правой колонке; проп `top` удалить из `DocumentPane`, `ReviewBar.tsx` после переноса `EXPERT` в `export.ts`-импорт остаётся источником констант `EXPERT`.)

- [ ] **Step 6: Запустить тесты — должны пройти**

Run: `npm --prefix frontend test -- src/platform/report && npx --prefix frontend tsc -b frontend`
Expected: PASS (5 тестов).

- [ ] **Step 7: Commit**

```bash
git add frontend
git commit -m "Отчёт в три колонки: замечания · документы · панель замечания с вердиктом"
```

---

### Task 8: Палитра команд ⌘K

**Files:**
- Create: `frontend/src/platform/shell/CommandMenu.tsx`, `frontend/src/platform/shell/commands.ts`
- Modify: `frontend/src/platform/shell/AppShell.tsx`, `frontend/package.json`
- Test: `frontend/src/platform/shell/commands.test.ts`

**Interfaces:**
- Consumes: `useChecks` (lib/queries), `useTheme`, `useSession`, `fieldName` (lib/labels); текущий отчёт — из кэша `queryClient.getQueryData(["check", id])`.
- Produces:
  - `buildCommands(input: { checks: CheckRow[]; report: Report | null; checkId: string | null; theme: "light" | "dark"; canSignOut: boolean }): Command[]`, `Command = { id: string; group: "Действия" | "Проверки" | "Замечания"; label: string; run: { type: "go"; to: string } | { type: "export" } | { type: "theme" } | { type: "signout" } | { type: "finding"; index: number } }`
  - `<CommandMenu />` — открывается по ⌘K / Ctrl+K и кнопке «Поиск» в шапке.
  - Переход к замечанию: `/app/checks/:id?f=<index>`; `ReportPage` при наличии `f` выбирает `report.findings[f]`.

- [ ] **Step 1: Установить cmdk**

```bash
npm --prefix frontend install --save-exact cmdk@<v>
```

- [ ] **Step 2: Написать падающий тест**

`frontend/src/platform/shell/commands.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { CheckRow, Report } from "../../lib/types";
import { buildCommands } from "./commands";

const check = { id: "a".repeat(32), title: "ЖК «Алатау»" } as CheckRow;
const report = { findings: [{ field: "total_area_m2", verdict: "MISMATCH" }, { field: "floors", verdict: "MATCH" }] } as unknown as Report;

describe("command menu", () => {
  it("offers actions, checks and — inside a report — its findings", () => {
    const cmds = buildCommands({ checks: [check], report, checkId: "a".repeat(32), theme: "light", canSignOut: true });
    expect(cmds.filter(c => c.group === "Действия").map(c => c.label)).toEqual(["Новая проверка", "Скачать XLSX", "Переключить тему", "Выйти"]);
    expect(cmds.find(c => c.group === "Проверки")).toMatchObject({ label: "ЖК «Алатау»", run: { type: "go", to: "/app/checks/" + "a".repeat(32) } });
    expect(cmds.filter(c => c.group === "Замечания").map(c => c.label)).toEqual(["Общая площадь, м²"]);
  });

  it("outside a report there is no export and no findings; without login no sign-out", () => {
    const cmds = buildCommands({ checks: [], report: null, checkId: null, theme: "dark", canSignOut: false });
    expect(cmds.map(c => c.label)).toEqual(["Новая проверка", "Переключить тему"]);
  });
});
```

- [ ] **Step 3: Запустить — убедиться, что падает**

Run: `npm --prefix frontend test -- src/platform/shell`
Expected: FAIL — `./commands` не найден.

- [ ] **Step 4: Реализация**

`frontend/src/platform/shell/commands.ts`:

```ts
import { t } from "../../lib/i18n";
import { fieldName } from "../../lib/labels";
import type { CheckRow, Report } from "../../lib/types";

export type CommandRun =
  | { type: "go"; to: string } | { type: "export" } | { type: "theme" } | { type: "signout" } | { type: "finding"; index: number };
export interface Command { id: string; group: "Действия" | "Проверки" | "Замечания"; label: string; run: CommandRun }

export function buildCommands(i: { checks: CheckRow[]; report: Report | null; checkId: string | null; theme: "light" | "dark"; canSignOut: boolean }): Command[] {
  const out: Command[] = [{ id: "new", group: "Действия", label: t("cmd.new"), run: { type: "go", to: "/app/new" } }];
  if (i.report) out.push({ id: "export", group: "Действия", label: t("cmd.export"), run: { type: "export" } });
  out.push({ id: "theme", group: "Действия", label: t("cmd.theme"), run: { type: "theme" } });
  if (i.canSignOut) out.push({ id: "signout", group: "Действия", label: t("cmd.signout"), run: { type: "signout" } });
  for (const c of i.checks) out.push({ id: `check-${c.id}`, group: "Проверки", label: c.title, run: { type: "go", to: `/app/checks/${c.id}` } });
  i.report?.findings.forEach((f, index) => {
    if (f.verdict !== "MATCH") out.push({ id: `finding-${index}`, group: "Замечания", label: fieldName(f.field), run: { type: "finding", index } });
  });
  return out;
}
```

`frontend/src/platform/shell/CommandMenu.tsx`:

```tsx
import { useQueryClient } from "@tanstack/react-query";
import { Command as Cmdk } from "cmdk";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { useSession } from "../../app/providers";
import Dialog from "../../design/Dialog";
import Kbd from "../../design/Kbd";
import { useTheme } from "../../design/theme";
import { exportXlsx } from "../../lib/export";
import { t } from "../../lib/i18n";
import { useChecks } from "../../lib/queries";
import type { CheckStatus } from "../../lib/types";
import { buildCommands, type Command } from "./commands";

export default function CommandMenu() {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const loc = useLocation();
  const qc = useQueryClient();
  const session = useSession();
  const { resolved, setTheme } = useTheme();
  const checks = useChecks();
  const checkId = loc.pathname.match(/^\/app\/checks\/([0-9a-f]{32})/)?.[1] ?? null;
  const data = checkId ? qc.getQueryData<CheckStatus>(["check", checkId]) : undefined;
  const report = data?.status === "done" ? data : null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(o => !o); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const cmds = buildCommands({ checks: checks.data ?? [], report: report?.report ?? null, checkId, theme: resolved, canSignOut: session.enabled });
  const run = (c: Command) => {
    setOpen(false);
    switch (c.run.type) {
      case "go": nav(c.run.to); break;
      case "finding": nav(`/app/checks/${checkId}?f=${c.run.index}`); break;
      case "export": if (report && checkId) exportXlsx(report.report, report.reviews ?? {}, checkId); break;
      case "theme": setTheme(resolved === "dark" ? "light" : "dark"); break;
      case "signout": session.signOut(); break;
    }
  };
  const groups = ["Действия", "Проверки", "Замечания"] as const;

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}
        className="flex items-center gap-2 min-h-8 px-2.5 border border-control rounded bg-sheet text-ink-2 text-sm w-72">
        {t("search.hint")} <span className="flex-1" /><Kbd>⌘K</Kbd>
      </button>
      <Dialog open={open} onOpenChange={setOpen} title={t("search.hint")}>
        <Cmdk label={t("search.hint")} className="flex flex-col">
          <Cmdk.Input placeholder={t("search.placeholder")} className="m-3 min-h-9 border border-control rounded px-2.5 bg-sheet" />
          <Cmdk.List className="max-h-80 overflow-auto px-2 pb-2">
            <Cmdk.Empty className="p-3 text-ink-2">Ничего не найдено</Cmdk.Empty>
            {groups.map(g => {
              const items = cmds.filter(c => c.group === g);
              return items.length ? (
                <Cmdk.Group key={g} heading={g} className="[&_[cmdk-group-heading]]:font-cond [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:text-ink-2 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pt-2">
                  {items.map(c => (
                    <Cmdk.Item key={c.id} value={`${c.label} ${c.id}`} onSelect={() => run(c)}
                      className="px-2 py-1.5 rounded cursor-pointer data-[selected=true]:bg-blue-wash">{c.label}</Cmdk.Item>
                  ))}
                </Cmdk.Group>
              ) : null;
            })}
          </Cmdk.List>
        </Cmdk>
      </Dialog>
    </>
  );
}
```

`AppShell.tsx`: заменить `<span id="shell-search" className="flex-1" />` на `<CommandMenu /><span className="flex-1" />` (+ импорт).

`ReportPage.tsx` (`ReportBody`): выбор замечания из `?f=`:

```tsx
const [params] = useSearchParams();
useEffect(() => {
  const f = Number(params.get("f"));
  if (params.has("f") && report.findings[f]) pick(report.findings[f]);
}, [params]);
```

(+ `useSearchParams` в импорт из `react-router`).

- [ ] **Step 5: Запустить тесты — должны пройти**

Run: `npm --prefix frontend test && npx --prefix frontend tsc -b frontend`
Expected: все PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "Палитра команд ⌘K: проверки, замечания, экспорт, тема, выход"
```

---

### Task 9: Уборка, e2e и бюджеты

**Files:**
- Delete: `frontend/src/App.tsx`, `frontend/src/styles.css`, `frontend/src/components/` (всё оставшееся: `Findings.tsx`, `Intake.tsx`, `ReportView.tsx`)
- Modify: `frontend/src/platform/auth/Login.tsx`, `frontend/src/platform/auth/SetPassword.tsx` (классы → Tailwind), `README.md` (раздел запуска)
- Create: `frontend/playwright.config.ts`, `frontend/e2e/platform.spec.ts`, `frontend/scripts/check-budget.mjs`
- Modify: `frontend/package.json` (`e2e`, `budget` скрипты)

**Interfaces:**
- Consumes: всё из Task 1–8; локальный бэкенд (`uv run uvicorn api.main:app --port 8000`, без Supabase — вход выключен).

- [ ] **Step 1: Удалить старый интерфейс**

```bash
git rm frontend/src/App.tsx frontend/src/styles.css frontend/src/components/Findings.tsx frontend/src/components/Intake.tsx frontend/src/components/ReportView.tsx
```

В `Login.tsx` и `SetPassword.tsx`: `<section className="intake login">` → `<section className="max-w-md mx-auto my-[10vh] px-4 flex flex-col gap-4">`; `<h1>` → `className="text-2xl font-semibold"`; `<input>` → `className="min-h-9 border border-control rounded px-2.5 bg-sheet"`; `<label>` → `className="flex flex-col gap-1 text-sm text-ink-2"`; кнопки → `Button` (`variant="primary"` для отправки, `variant="ghost"` для «Забыли пароль?»); `.status.error` → `className="text-pencil text-sm"`.

Проверка: `npx --prefix frontend tsc -b frontend && npm --prefix frontend test` — без ошибок.

- [ ] **Step 2: Playwright**

```bash
npm --prefix frontend install --save-exact -D @playwright/test@<v>
npx --prefix frontend playwright install chromium
```

`frontend/playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: "http://localhost:5173", viewport: { width: 1366, height: 768 } },
  webServer: [
    { command: "cd .. && uv run uvicorn api.main:app --port 8000", port: 8000, reuseExistingServer: true, timeout: 60_000 },
    { command: "npm run dev", port: 5173, reuseExistingServer: true },
  ],
});
```

`frontend/e2e/platform.spec.ts`:

```ts
import { expect, test } from "@playwright/test";
import path from "node:path";

const SAMPLE = path.resolve(__dirname, "../../data/synthetic/samples/ru/ru_00001/text");

test("upload → sections → report → verdict → back to the list", async ({ page }) => {
  await page.goto("/app/new");
  await page.setInputFiles('input[type="file"]', ["PZ.pdf", "AR.pdf", "KR.pdf", "SMETA.pdf"].map(f => path.join(SAMPLE, f)));
  await expect(page.getByRole("heading", { name: "Проверьте разделы перед запуском" })).toBeVisible();
  await page.getByRole("button", { name: /Проверить 4/ }).click();
  await expect(page).toHaveURL(/\/app\/checks\/[0-9a-f]{32}$/);
  await expect(page.getByRole("heading", { name: "Общая площадь, м²" })).toBeVisible({ timeout: 30_000 });
  await page.keyboard.press("1");
  await expect(page.getByText("1/4")).toBeVisible();
  await page.getByRole("link", { name: "Проверки" }).click();
  await expect(page.getByRole("row").filter({ hasText: "1/4" })).toBeVisible();
});

test("old ?check= link opens the report", async ({ page, request }) => {
  const { id } = await (await request.post("http://localhost:8000/api/demo/ru")).json();
  await page.goto(`/?check=${id}`);
  await expect(page).toHaveURL(new RegExp(`/app/checks/${id}$`));
});

test("⌘K jumps to a check", async ({ page }) => {
  await page.goto("/app");
  await page.keyboard.press("Control+k");
  await page.getByPlaceholder("Найти проверку или замечание…").fill("Новая");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/app\/new$/);
});
```

В `frontend/package.json` → `"scripts"`: `"e2e": "playwright test"`.

- [ ] **Step 3: Бюджет сборки**

`frontend/scripts/check-budget.mjs`:

```js
// Platform chunks must not pull three.js, and the entry stays small (spec §7).
import { readdirSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const dir = new URL("../dist/assets/", import.meta.url);
const files = readdirSync(dir).filter(f => f.endsWith(".js"));
const entry = files.find(f => /^index-.*\.js$/.test(f));
const kb = f => gzipSync(readFileSync(new URL(f, dir))).length / 1024;
let failed = false;
if (kb(entry) > 200) { console.error(`entry ${entry}: ${kb(entry).toFixed(0)} KB gzip > 200`); failed = true; }
// three.js ships the WebGLRenderer class: only the landing scene chunk (plan 2) may contain it
for (const f of files) if (readFileSync(new URL(f, dir), "utf8").includes("WebGLRenderer") && !/scene/i.test(f)) {
  console.error(`${f} pulls three.js into the platform`); failed = true;
}
console.log(files.map(f => `${f}: ${kb(f).toFixed(0)} KB`).join("\n"));
process.exit(failed ? 1 : 0);
```

`"budget": "vite build && node scripts/check-budget.mjs"` в `scripts`.

- [ ] **Step 4: Прогнать всё**

Run:
```bash
npm --prefix frontend test
npm --prefix frontend run budget
npm --prefix frontend run e2e
uv run pytest -q tests/test_api_store.py tests/test_pipeline.py
```
Expected: всё PASS; бюджет — entry ≤ 200 KB gzip, без three.js.

- [ ] **Step 5: Тексты платформы — в словарь**

Найти русские строки прямо в разметке платформы:

```bash
grep -rnP '(>|"|`)[^<>{}"`]*[А-Яа-яЁё][^<>{}"`]*(<|"|`)' frontend/src/platform frontend/src/app --include=*.tsx | grep -v 'aria-label=\|title=' | grep -v '\.test\.tsx'
```

Каждую найденную строку («Загрузка…», «Список не загрузился», «Начать заново», «всё сходится», «сохраняем…», «Ничего не найдено», подписи сводки «Разделы» / «Расхождения» / «Нет значения» / «Совпало» / «Эксперт» и т.п.) перенести в `RU` в `lib/i18n.ts` под ключ вида `<экран>.<что>` и заменить на `t("…")`. Подписи `aria-label` / `title` — тоже через `t`. Повторить grep — результат пуст (кроме тестов). Прогнать `npm --prefix frontend test` — тесты ищут те же тексты, значения не меняются.

- [ ] **Step 6: Ручная проверка в браузере**

Запустить бэкенд и `npm --prefix frontend run dev`; открыть `/app` на 375 / 1366 / 1920 px, обе темы (настройки → тема): список, мастер, отчёт (клавиши `j`/`k`/`1`/`2`/`←`/`→`/`s`, ⌘K), отчёт без замечаний (демо, где все совпали — либо фильтр «Подтверждённые» на свежей проверке), длинное название (переименовать на 200 символов). Сделать скриншоты.

- [ ] **Step 7: README и commit**

В `README.md`, раздел «MVP: веб-сервис сверки ТЭП» — заменить абзац про клавиши на:

```
Интерфейс: `/app` — мои проверки, `/app/new` — новая проверка (файлы → разделы → проверка), `/app/checks/<id>` — отчёт
в три колонки. Клавиши: `j`/`k` — замечания, `←`/`→` — места, `s` — рядом/по одному, `1`/`2` — вердикт, `⌘K` — поиск
и команды. Тесты фронта: `npm --prefix frontend test`, сквозные — `npm --prefix frontend run e2e`.
```

```bash
git add -A frontend README.md
git commit -m "Старый интерфейс удалён; e2e Playwright и бюджет сборки"
```

---

## Перед слиянием в `main`

- [ ] Применить миграцию `supabase/migrations/20261011120000_checks_title.sql` в Supabase (SQL Editor или подключение).
- [ ] Предпросмотр Vercel ветки `frontend-redesign`: вход, список, мастер, отчёт, ⌘K, PDF по подписанной ссылке.
- [ ] Слить в `main` (fast-forward или merge), проверить прод.
