import { useState } from "react";
import Button from "../../design/Button";
import { SECTION, SECTIONS, SECTION_FULL } from "../../lib/labels";
import type { Choice, Section, UploadedFile } from "../../lib/types";
import { t } from "../../lib/i18n";

const HOW: Record<string, string> = {
  title: t("review.how.title"), "document code": t("review.how.code"), "table signature": t("review.how.table"),
  unknown: t("review.how.unknown"), scan: t("review.how.scan"), unreadable: t("review.how.unreadable"),
  user: t("review.how.user"),
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
      <h1 id="review-title" className="text-xl font-semibold">{t("review.title")}</h1>
      <p className="text-ink-2">{t("review.lead")}</p>
      <table className="w-full bg-sheet border border-line text-sm">
        <thead><tr className="text-left font-cond text-[11px] uppercase tracking-wide text-ink-2"><th className="p-2">{t("review.col.file")}</th><th className="p-2">{t("review.col.detected")}</th><th className="p-2">{t("review.col.section")}</th></tr></thead>
        <tbody>
          {names.map(n => {
            const f = files[n];
            return (
              <tr key={n} className="border-t border-line">
                <td className="p-2 font-medium break-all">{n}</td>
                <td className="p-2 text-ink-2">{f.section ? `${SECTION[f.section]}, ${HOW[f.how] ?? f.how}` : HOW[f.how] ?? f.how}</td>
                <td className="p-2">
                  <select className="min-h-[26px] border border-control rounded px-1.5 bg-sheet max-w-full" aria-label={t("review.fileSection", { name: n })} value={choice[n]} disabled={busy}
                    onChange={e => setChoice(c => ({ ...c, [n]: e.target.value as Choice }))}>
                    <option value="auto">{f.section ? t("review.asDetected", { section: SECTION[f.section] }) : t("review.detectLater")}</option>
                    {SECTIONS.map(s => <option key={s} value={s}>{SECTION_FULL[s]}</option>)}
                    <option value="skip">{t("review.skip")}</option>
                  </select>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {missing.length > 0 && (
        <div className="border-l-[3px] border-amber bg-amber-wash px-3 py-2 text-sm">{t("review.missing", { list: missing.map(s => SECTION_FULL[s]).join(", ") })}</div>
      )}
      {twice.map(([s, ns]) => (
        <div key={s} className="border-l-[3px] border-amber bg-amber-wash px-3 py-2 text-sm">{t("review.twice", { section: SECTION_FULL[s], files: ns.join(", ") })}</div>
      ))}
      {unknown.length > 0 && (
        <div className="border-l-[3px] border-amber bg-amber-wash px-3 py-2 text-sm">{t("review.unknown", { files: unknown.join(", ") })}</div>
      )}
      <div className="flex gap-2">
        <Button variant="primary" disabled={busy || !used.length} onClick={() => onStart(choice)}>
          {t("review.start", { n: used.length })}
        </Button>
        <Button variant="ghost" disabled={busy} onClick={onCancel}>{t("common.cancel")}</Button>
      </div>
      <div className={status?.error ? "text-pencil text-sm" : "text-ink-2 text-sm"} role="status" aria-live="polite">{status?.text}</div>
    </section>
  );
}
