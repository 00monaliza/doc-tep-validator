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
  if (!MISMATCH && !MISSING) return <span className="text-green">{t("checks.allMatch")}</span>;
  return (
    <span className="num">
      {MISMATCH > 0 && <span className="text-pencil font-semibold">{MISMATCH} ≠</span>}
      {MISMATCH > 0 && MISSING > 0 && " · "}
      {MISSING > 0 && <span className="text-amber">{t("checks.missing", { n: MISSING })}</span>}
    </span>
  );
}

export default function ChecksTable({ rows, onRename }: { rows: CheckRow[]; onRename: (id: string, title: string) => void }) {
  const [editing, setEditing] = useState<CheckRow | null>(null);
  const [title, setTitle] = useState("");
  const save = () => { if (editing && title.trim()) onRename(editing.id, title.trim()); setEditing(null); };

  return (
    <>
      <ul className="md:hidden flex flex-col gap-2">
        {rows.map(r => (
          <li key={r.id} className="bg-sheet border border-line rounded p-3 flex flex-col gap-1.5">
            <Link to={`/app/checks/${r.id}`} title={r.title} className="font-semibold text-ink break-words">{r.title}</Link>
            <span className="flex gap-1">{SECTIONS.map(s => <SectionChip key={s} section={s} present={r.sections.includes(s)} />)}</span>
            <span className="flex flex-wrap gap-x-3 text-sm"><Result r={r} /><span className="text-ink-2">{date(r.created_at)} → {date(r.expires_at)}</span></span>
          </li>
        ))}
      </ul>
      <table className="hidden md:table w-full table-fixed border-collapse bg-sheet border border-line text-sm">
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
          <input aria-label={t("checks.rename.field")} maxLength={200} value={title} onChange={e => setTitle(e.target.value)} autoFocus
            className="min-h-9 border border-control rounded px-2.5 bg-sheet" />
          <Button type="submit" variant="primary" className="self-start">{t("checks.rename.save")}</Button>
        </form>
      </Dialog>
    </>
  );
}
