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
