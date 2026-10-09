import type { CheckStatus, Report } from "./types";

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

export async function waitForReport(id: string, signal?: AbortSignal): Promise<Report> {
  for (;;) {
    const r = await fetch(`/api/checks/${id}`, { signal });
    if (!r.ok) throw new Error("Проверка не найдена. Загрузите документы заново.");
    const s: CheckStatus = await r.json();
    if (s.status === "done") return s.report;
    if (s.status === "error") throw new Error(`Проверка не выполнена: ${s.error}`);
    await new Promise(res => setTimeout(res, 800));
  }
}
