import { useState } from "react";
import Button from "../../design/Button";
import { SECTION, SECTIONS, SECTION_FULL } from "../../lib/labels";
import type { Choice, Section, UploadedFile } from "../../lib/types";

const HOW: Record<string, string> = {
  title: "по заголовку", "document code": "по шифру документа", "table signature": "по таблице",
  unknown: "не определён", scan: "скан: определится после распознавания", unreadable: "файл не читается",
  user: "выбран вручную",
};

interface Props {
  files: Record<string, UploadedFile>;
  busy: boolean;
  status: { text: string; error?: boolean } | null;
  onStart: (choices: Record<string, Choice>) => void;
  onCancel: () => void;
}

/** The uploaded files before the check: the detected section of each, which the user may correct. */
export default function FileReview({ files, busy, status, onStart, onCancel }: Props) {
  const names = Object.keys(files).sort();
  const [choice, setChoice] = useState<Record<string, Choice>>(
    () => Object.fromEntries(names.map(n => [n, files[n].use ? "auto" : "skip"])));

  const sectionOf = (n: string): Section | null =>
    choice[n] === "skip" ? null : choice[n] === "auto" ? files[n].section : (choice[n] as Section);
  const used = names.filter(n => choice[n] !== "skip");
  const bySection = new Map<Section, string[]>();
  for (const n of used) {
    const s = sectionOf(n);
    if (s) bySection.set(s, [...(bySection.get(s) ?? []), n]);
  }
  const missing = SECTIONS.filter(s => !bySection.has(s));
  const twice = [...bySection].filter(([, ns]) => ns.length > 1);
  const unknown = used.filter(n => !sectionOf(n));

  return (
    <section className="max-w-3xl flex flex-col gap-3" aria-labelledby="review-title">
      <h1 id="review-title" className="text-xl font-semibold">Проверьте разделы перед запуском</h1>
      <p className="text-ink-2">Раздел каждого файла определён по первой странице. Если он неверный, выберите нужный; лишний файл можно не учитывать.</p>
      <table className="w-full bg-sheet border border-line text-sm">
        <thead><tr className="text-left font-cond text-[11px] uppercase tracking-wide text-ink-2"><th className="p-2">Файл</th><th className="p-2">Определено</th><th className="p-2">Раздел</th></tr></thead>
        <tbody>
          {names.map(n => {
            const f = files[n];
            return (
              <tr key={n} className="border-t border-line">
                <td className="p-2 font-medium break-all">{n}</td>
                <td className="p-2 text-ink-2">{f.section ? `${SECTION[f.section]}, ${HOW[f.how] ?? f.how}` : HOW[f.how] ?? f.how}</td>
                <td className="p-2">
                  <select className="min-h-[26px] border border-control rounded px-1.5 bg-sheet max-w-full" aria-label={`Раздел файла ${n}`} value={choice[n]} disabled={busy}
                    onChange={e => setChoice(c => ({ ...c, [n]: e.target.value as Choice }))}>
                    <option value="auto">{f.section ? `как определено (${SECTION[f.section]})` : "определить при проверке"}</option>
                    {SECTIONS.map(s => <option key={s} value={s}>{SECTION_FULL[s]}</option>)}
                    <option value="skip">не учитывать</option>
                  </select>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {missing.length > 0 && (
        <div className="border-l-[3px] border-amber bg-amber-wash px-3 py-2 text-sm">Нет в пакете: {missing.map(s => SECTION_FULL[s]).join(", ")}. Сверка с ними будет пропущена.</div>
      )}
      {twice.map(([s, ns]) => (
        <div key={s} className="border-l-[3px] border-amber bg-amber-wash px-3 py-2 text-sm">{SECTION_FULL[s]}: {ns.join(", ")}. Учтётся только первый файл раздела.</div>
      ))}
      {unknown.length > 0 && (
        <div className="border-l-[3px] border-amber bg-amber-wash px-3 py-2 text-sm">Раздел не определён: {unknown.join(", ")}. Выберите его, иначе файл не попадёт в сверку.</div>
      )}
      <div className="flex gap-2">
        <Button variant="primary" disabled={busy || !used.length} onClick={() => onStart(choice)}>
          Проверить {used.length} файл(ов)
        </Button>
        <Button variant="ghost" disabled={busy} onClick={onCancel}>Отмена</Button>
      </div>
      <div className={status?.error ? "text-pencil text-sm" : "text-ink-2 text-sm"} role="status" aria-live="polite">{status?.text}</div>
    </section>
  );
}
