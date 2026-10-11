import { accessToken } from "./auth";
import type { CheckStatus, Choice, Report, Review, Reviews, UploadedFile } from "./types";

/** Raised by any API call the server refused for a missing or expired login. */
export class Unauthorized extends Error {}

/** fetch with the Supabase access token (when there is a login); 401 becomes Unauthorized. */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = await accessToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const r = await fetch(input, { ...init, headers });
  if (r.status === 401) {
    const body = await r.json().catch(() => ({}));
    throw new Unauthorized(body.detail ?? "Нужно войти");
  }
  return r;
}

/** A URL the PDF viewer can open by itself: a signed Storage URL when there is a login. */
export async function fileLink(checkId: string, name: string): Promise<string> {
  const r = await apiFetch(`/api/checks/${checkId}/files/${encodeURIComponent(name)}/link`);
  if (!r.ok) throw new Error(`Файл ${name} не открылся: сервер ответил ${r.status}`);
  return (await r.json()).url;
}

async function json<T>(req: Promise<Response>, fallback: string): Promise<T> {
  const r = await req;
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Сервер ответил ${r.status}. ${fallback}`);
  return body;
}

const startCheck = async (req: Promise<Response>) => (await json<{ id: string }>(req, "Файлы не приняты.")).id;

function put(url: string, file: File, onSent: (bytes: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest(); // fetch has no upload progress
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
    xhr.upload.onprogress = e => onSent(e.loaded);
    xhr.onload = () => (xhr.status < 300 ? resolve()
      : reject(new Error(`${file.name}: хранилище ответило ${xhr.status}`)));
    xhr.onerror = () => reject(new Error(`${file.name}: сеть прервалась при загрузке`));
    xhr.send(file);
  });
}

/** Uploads the files straight to storage (past the 4.5 MB limit of a Vercel function), without
 * starting the check: the answer has the section detected for each file. */
export async function uploadFiles(
  files: FileList | File[], onProgress: (sent: number, total: number) => void,
): Promise<{ id: string; files: Record<string, UploadedFile> }> {
  const list = [...files];
  const { id, uploads } = await json<{ id: string; uploads: Record<string, string> }>(apiFetch("/api/checks/init", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ files: list.map(f => ({ name: f.name, size: f.size })) }),
  }), "Файлы не приняты.");
  const total = list.reduce((s, f) => s + f.size, 0);
  const sent = new Map<string, number>();
  const report = () => onProgress([...sent.values()].reduce((s, b) => s + b, 0), total);
  await Promise.all(list.map(f => put(uploads[f.name], f, b => { sent.set(f.name, b); report(); })));
  return json(apiFetch(`/api/checks/${id}/uploaded`, { method: "POST" }), "Файлы не приняты.");
}

export function startUploaded(id: string, files: Record<string, Choice>): Promise<string> {
  return startCheck(apiFetch(`/api/checks/${id}/start`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ files }),
  }));
}

export function startDemo(lang: "ru" | "kz", kind: "text" | "scan"): Promise<string> {
  return startCheck(apiFetch(`/api/demo/${lang}?kind=${kind}`, { method: "POST" }));
}

export type Outcome =
  | { kind: "report"; report: Report; reviews: Reviews }
  | { kind: "uploaded"; files: Record<string, UploadedFile> };

/** Polls a check until it has a report, or reports that it still waits for the user's start. */
export async function waitForCheck(id: string, signal?: AbortSignal): Promise<Outcome> {
  for (;;) {
    const r = await apiFetch(`/api/checks/${id}`, { signal });
    if (!r.ok) throw new Error("Проверка не найдена. Загрузите документы заново.");
    const s: CheckStatus = await r.json();
    if (s.status === "done") return { kind: "report", report: s.report, reviews: s.reviews ?? {} };
    if (s.status === "uploaded") return { kind: "uploaded", files: s.files };
    if (s.status === "receiving") throw new Error("Загрузка файлов не была завершена. Загрузите документы заново.");
    if (s.status === "error") throw new Error(`Проверка не выполнена: ${s.error}`);
    await new Promise(res => setTimeout(res, 800));
  }
}

export interface Capabilities { ocr: boolean; auth: { url: string; key: string } | null }

export async function getCapabilities(): Promise<Capabilities> {
  try {
    const r = await fetch("/api/capabilities");
    return r.ok ? await r.json() : { ocr: true, auth: null };
  } catch {
    return { ocr: true, auth: null }; // unknown: do not hide anything
  }
}

export async function saveReview(checkId: string, finding: number, review: Review): Promise<void> {
  const r = await apiFetch(`/api/checks/${checkId}/reviews/${finding}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(review),
  });
  if (!r.ok) throw new Error(`Вердикт не сохранён: сервер ответил ${r.status}`);
}
