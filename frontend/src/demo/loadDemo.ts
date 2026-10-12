import type { Report } from "../lib/types";

export async function loadDemo(): Promise<{ report: Report; title: string }> {
  const r = await fetch("/demo-data/report.json");
  if (!r.ok) throw new Error(`демо не загрузилось: ${r.status}`);
  const report = (await r.json()) as Report & { title: string };
  return { report, title: report.title };
}
