import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useParams, useSearchParams } from "react-router";
import Button from "../../design/Button";
import EmptyState from "../../design/EmptyState";
import SectionChip from "../../design/SectionChip";
import StampSummary from "../../design/StampSummary";
import { useToast } from "../../design/Toast";
import { saveReview, Unauthorized } from "../../lib/api";
import { exportXlsx } from "../../lib/export";
import { t } from "../../lib/i18n";
import { SECTIONS } from "../../lib/labels";
import { useQueryClient } from "@tanstack/react-query";
import { toLogin, useCheck, withReview } from "../../lib/queries";
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
  if (state.kind === "loading") return <p className="p-6 text-ink-2">{t("common.loading")}</p>;
  if (state.kind === "redirect") return <Navigate to={state.to} replace />;
  if (state.kind === "message") return <EmptyState title={state.text} />;
  return <ReportBody checkId={id} report={state.data.report} title={state.data.title ?? ""} initial={state.data.reviews ?? {}} />;
}

export function ReportBody({ checkId, report, title, initial, onSave }: {
  checkId: string; report: Report; title: string; initial: Reviews;
  onSave?: (finding: number, r: Review) => Promise<void>; // the demo keeps verdicts in the page
}) {
  const toast = useToast();
  const qc = useQueryClient();
  const [reviews, setReviews] = useState<Reviews>(initial);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState<Filter>(NO_FILTER);
  const [matchesOpen, setMatchesOpen] = useState(false);
  const queue = useRef(createReviewQueue((n, r) => (onSave ?? ((f, rv) => saveReview(checkId, f, rv)))(n, r)));
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
    queue.current.push(Number(key), next).then(() => {
      qc.setQueryData<CheckStatus>(["check", checkId], d => (d ? withReview(d, Number(key), next) : d));
    }, e => {
      if (e instanceof Unauthorized) { toLogin(e); return; }
      setReviews(r => { const { [key]: _, ...rest } = r; return prev ? { ...rest, [key]: prev } : rest; });
      toast((e as Error).message, "error");
    }).finally(() => setSaving(false));
  };
  const toggleVerdict = (f: Finding, v: ExpertVerdict) => {
    const r = reviewOf(f) ?? EMPTY;
    review(f, { ...r, verdict: r.verdict === v ? null : v });
  };
  // ⌘K → «Замечание»: /app/checks/:id?f=<index in report.findings>
  const [params] = useSearchParams();
  useEffect(() => {
    const f = Number(params.get("f"));
    if (params.has("f") && report.findings[f]) pick(report.findings[f]);
  }, [params]);
  useReportKeys({ list: matchesOpen ? [...bad, ...ok] : bad, current, pick, toggleVerdict, enabled: true });

  const s = report.summary, c = report.completeness;
  const reviewed = allBad.filter(f => reviewOf(f)?.verdict).length;
  return (
    <div className="flex flex-col lg:h-full">
      <header className="flex flex-wrap items-center gap-2 md:gap-3 px-3 md:px-4 py-2 bg-sheet border-b border-line">
        <h1 className="text-lg font-semibold truncate max-w-full lg:max-w-[40%]" title={title}>{title}</h1>
        <span className="flex gap-1">{SECTIONS.map(x => <SectionChip key={x} section={x} present={c.present.includes(x)} />)}</span>
        <span className="flex-1" />
        <Button size="sm" onClick={() => exportXlsx(report, reviews, checkId).catch(e => toast((e as Error).message, "error"))}>{t("report.export")}</Button>
      </header>
      <div className="px-3 md:px-4 py-2"><StampSummary items={[
        { label: t("stamp.sections"), value: `${c.present.length}/${c.required.length}`, tone: c.missing.length ? "bad" : "ok" },
        { label: t("stamp.mismatch"), value: String(s.MISMATCH), tone: s.MISMATCH ? "bad" : "ok" },
        { label: t("stamp.missing"), value: String(s.MISSING), tone: s.MISSING ? "warn" : "ok" },
        { label: t("stamp.match"), value: String(s.MATCH) },
        { label: t("stamp.expert"), value: `${reviewed}/${allBad.length}`, tone: allBad.length && reviewed === allBad.length ? "ok" : undefined },
      ]} /></div>
      <div className="lg:flex-1 lg:min-h-0 grid grid-cols-1 lg:grid-cols-[minmax(280px,30%)_1fr_minmax(260px,24%)] border-t border-line">
        <aside className="max-h-[50vh] lg:max-h-none min-h-0 overflow-auto bg-sheet lg:border-r border-b lg:border-b-0 border-line">
          <FindingsColumn report={report} bad={bad} ok={ok} filter={filter} onFilter={setFilter} matchesOpen={matchesOpen}
            onMatchesOpen={setMatchesOpen} current={current} onPick={pick} reviewOf={reviewOf}
            onPickRefs={refs => setSelection({ refs })} />
        </aside>
        <DocumentPane checkId={checkId} report={report} selection={selection} />
        <aside className="min-h-0 overflow-auto bg-sheet lg:border-l border-t lg:border-t-0 border-line">
          <FindingDetail finding={current} review={(current && reviewOf(current)) ?? EMPTY} saving={saving}
            onReview={r => current && review(current, r)} />
        </aside>
      </div>
    </div>
  );
}
