import type { CheckStatus, Report, Review, Reviews } from "./types";

export const fileUrl = (checkId: string, name: string) =>
  `/api/checks/${checkId}/files/${encodeURIComponent(name)}`;

async function startCheck(req: Promise<Response>): Promise<string> {
  const r = await req;
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail ?? `Сервер ответил ${r.status}. Файлы не приняты.`);
  return body.id;
}

export function uploadFiles(files: FileList | File[]): Promise<string> {
  const fd = new FormData();
  [...files].forEach(f => fd.append("files", f));
  return startCheck(fetch("/api/checks", { method: "POST", body: fd }));
}

export function startDemo(lang: "ru" | "kz", kind: "text" | "scan"): Promise<string> {
  return startCheck(fetch(`/api/demo/${lang}?kind=${kind}`, { method: "POST" }));
}

export async function waitForReport(id: string, signal?: AbortSignal): Promise<{ report: Report; reviews: Reviews }> {
  for (;;) {
    const r = await fetch(`/api/checks/${id}`, { signal });
    if (!r.ok) throw new Error("Проверка не найдена. Загрузите документы заново.");
    const s: CheckStatus = await r.json();
    if (s.status === "done") return { report: s.report, reviews: s.reviews ?? {} };
    if (s.status === "error") throw new Error(`Проверка не выполнена: ${s.error}`);
    await new Promise(res => setTimeout(res, 800));
  }
}

export interface Capabilities { ocr: boolean }

export async function getCapabilities(): Promise<Capabilities> {
  try {
    const r = await fetch("/api/capabilities");
    return r.ok ? await r.json() : { ocr: true };
  } catch {
    return { ocr: true }; // unknown: do not hide anything
  }
}

export async function saveReview(checkId: string, finding: number, review: Review): Promise<void> {
  const r = await fetch(`/api/checks/${checkId}/reviews/${finding}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(review),
  });
  if (!r.ok) throw new Error(`Вердикт не сохранён: сервер ответил ${r.status}`);
}
