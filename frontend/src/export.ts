import type { Cell, Row } from "write-excel-file/browser";
import { SECTION, SECTIONS, SECTION_FULL, VERDICT, fieldName } from "./labels";
import { comparedLabel } from "./components/Findings";
import { EXPERT } from "./components/ReviewBar";
import type { Report, Reviews } from "./types";

const head = (titles: string[]): Row => titles.map(t => ({ value: t, fontWeight: "bold", wrap: true }) as Cell);
const text = (v: string | null | undefined): Cell => ({ value: v ?? "", wrap: true });
const num = (v: unknown): Cell =>
  typeof v === "number" ? { value: v } : { value: v == null ? "—" : String(v) };

/** The findings register (with the expert's verdicts), the extracted TEP and completeness, as one .xlsx. */
export async function exportXlsx(report: Report, reviews: Reviews, checkId: string): Promise<void> {
  const { default: writeXlsxFile } = await import("write-excel-file/browser"); // loaded only on export

  // the findings that need attention first, then the matching checks — in the order of the screen
  const order = [...report.findings.keys()].sort(
    (a, b) => Number(report.findings[a].verdict === "MATCH") - Number(report.findings[b].verdict === "MATCH"));
  const findings: Row[] = [head([
    "№", "Результат", "Показатель", "Здание", "Что сверяется", "Значения", "Где", "Расхождение, %",
    "Примечания", "Вердикт эксперта", "Комментарий эксперта",
  ])];
  order.forEach((i, n) => {
    const f = report.findings[i];
    const r = reviews[String(i)];
    findings.push([
      { value: n + 1 },
      text(VERDICT[f.verdict] + (f.needs_expert ? " (эксперту)" : "") + (f.low_confidence ? " (скан)" : "")),
      text(fieldName(f.field)),
      text(f.object_name),
      text(comparedLabel(f)),
      text(f.refs.map(x => `${x.label ?? SECTION[x.section]}: ${x.value ?? "—"}`).join("\n")),
      text(f.refs.map(x => `${x.label ?? SECTION[x.section]}: ${x.page ? `стр. ${x.page}` : "—"}`).join("\n")),
      f.delta_rel != null && f.verdict === "MISMATCH" ? { value: Math.round(f.delta_rel * 1000) / 10 } : text(""),
      text(f.notes.join("\n")),
      text(r?.verdict ? EXPERT[r.verdict] : ""),
      text(r?.comment),
    ]);
  });

  const objects = report.objects ?? {};
  const tep: Row[] = [head(["Раздел", "Здание", "Показатель", "Значение", "Как записано", "Страница"])];
  for (const s of SECTIONS) {
    for (const [k, e] of Object.entries(report.tep[s] ?? {})) {
      if (k.startsWith("room.")) continue;
      tep.push([
        text(SECTION_FULL[s]), text(e.object ? objects[e.object] ?? e.object : ""),
        text(fieldName(k.includes("/") ? k.split("/")[1] : k)), num(e.value ?? e.raw), text(e.raw),
        e.page ? { value: e.page } : text(""),
      ]);
    }
  }

  const c = report.completeness;
  const byS = Object.fromEntries(report.documents.filter(d => d.section).map(d => [d.section!, d]));
  const compl: Row[] = [head(["Раздел", "Файл", "Статус"])];
  for (const s of c.required) {
    const d = byS[s];
    compl.push([text(SECTION_FULL[s]), text(d ? d.file + (d.ocr ? " (скан)" : "") : ""),
      text(d ? "загружен" : "нет в пакете")]);
  }
  for (const f of c.unrecognised) compl.push([text("—"), text(f), text("раздел не определён")]);
  for (const f of c.duplicates) compl.push([text("—"), text(f), text("второй документ раздела, не учитывался")]);

  await writeXlsxFile([
    { data: findings, sheet: "Замечания", stickyRowsCount: 1,
      columns: [4, 14, 30, 22, 22, 30, 16, 12, 30, 16, 30].map(width => ({ width })) },
    { data: tep, sheet: "ТЭП", stickyRowsCount: 1, columns: [26, 24, 34, 14, 16, 10].map(width => ({ width })) },
    { data: compl, sheet: "Комплектность", stickyRowsCount: 1, columns: [28, 34, 30].map(width => ({ width })) },
  ]).toFile(`ТЭП-проверка-${checkId.slice(0, 8)}.xlsx`);
}
