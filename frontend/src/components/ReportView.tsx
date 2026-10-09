import { useCallback, useEffect, useMemo, useState } from "react";
import { saveReview } from "../api";
import { exportXlsx } from "../export";
import { LANG } from "../labels";
import type { ExpertVerdict, Finding, Ref, Report, Review, Reviews } from "../types";
import Completeness from "./Completeness";
import Findings, { NO_FILTER, applyFilter, type Filter } from "./Findings";
import ReviewBar from "./ReviewBar";
import TepTables from "./TepTables";
import Viewer from "./Viewer";

type Tab = "findings" | "tep" | "compl";

const EMPTY: Review = { verdict: null, comment: "" };

interface Props { checkId: string; report: Report; initialReviews: Reviews; onReset: () => void }

export default function ReportView({ checkId, report, initialReviews, onReset }: Props) {
  const [filter, setFilter] = useState<Filter>(NO_FILTER);
  const [reviews, setReviews] = useState<Reviews>(initialReviews);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const reviewOf = useCallback((f: Finding) => reviews[String(report.findings.indexOf(f))], [reviews, report]);
  const allBad = useMemo(() => report.findings.filter(f => f.verdict !== "MATCH"), [report]);
  const bad = useMemo(() => applyFilter(allBad, filter, reviewOf), [allBad, filter, reviewOf]);
  const ok = useMemo(
    () => applyFilter(report.findings.filter(f => f.verdict === "MATCH"), filter, reviewOf), [report, filter, reviewOf]);
  const reviewed = allBad.filter(f => reviewOf(f)?.verdict).length;
  const [tab, setTab] = useState<Tab>("findings");
  const [matchesOpen, setMatchesOpen] = useState(false);
  const [current, setCurrent] = useState<Finding | null>(bad[0] ?? null);
  const [selection, setSelection] = useState<{ refs: Ref[]; finding?: Finding } | null>(
    current ? { refs: current.refs, finding: current } : null,
  );
  const c = report.completeness;
  const s = report.summary;

  const pick = (f: Finding, fromTap = false) => {
    setCurrent(f);
    setSelection({ refs: f.refs, finding: f });
    if (ok.includes(f)) setMatchesOpen(true);
    // on a phone the document is below the list: a tap should show it
    if (fromTap && window.matchMedia("(max-width: 900px)").matches)
      setTimeout(() => document.querySelector(".viewer")?.scrollIntoView({ behavior: "smooth" }));
  };

  const review = async (f: Finding, next: Review) => {
    const key = String(report.findings.indexOf(f));
    const prev = reviews[key];
    setReviews(r => {  // optimistic: the list updates at once, a failed save rolls back
      const { [key]: _, ...rest } = r;
      return next.verdict || next.comment ? { ...rest, [key]: next } : rest;
    });
    setSaving(true);
    setSaveError("");
    try {
      await saveReview(checkId, Number(key), next);
    } catch (e) {
      setReviews(r => {
        const { [key]: _, ...rest } = r;
        return prev ? { ...rest, [key]: prev } : rest;
      });
      setSaveError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const toggleVerdict = (f: Finding, v: ExpertVerdict) => {
    const r = reviewOf(f) ?? EMPTY;
    review(f, { ...r, verdict: r.verdict === v ? null : v });
  };

  // a filter that hides the open finding moves the selection to the first one still shown
  useEffect(() => {
    if (current && !bad.includes(current) && !ok.includes(current) && bad[0]) pick(bad[0]);
  }, [filter]);

  // j/k walk the findings that pass the filter (о/л on the Russian layout)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (tab !== "findings" || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target instanceof HTMLElement && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
      if ((e.key === "1" || e.key === "2") && current) {
        e.preventDefault();
        toggleVerdict(current, e.key === "1" ? "confirmed" : "false_positive");
        return;
      }
      const step = e.key === "j" || e.key === "о" ? 1 : e.key === "k" || e.key === "л" ? -1 : 0;
      if (!step) return;
      const list = matchesOpen ? [...bad, ...ok] : bad;
      if (!list.length) return;
      e.preventDefault();
      const i = current ? list.indexOf(current) : -1;
      pick(list[i < 0 ? 0 : Math.min(list.length - 1, Math.max(0, i + step))]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const tabs: { id: Tab; label: string; count?: string | number }[] = [
    { id: "findings", label: "Замечания", count: bad.length },
    { id: "tep", label: "ТЭП" },
    { id: "compl", label: "Комплектность", count: c.missing.length ? `−${c.missing.length}` : "" },
  ];

  return (
    <div className="app">
      <header className="stamp">
        <div className="title">
          <small>Проверка пакета</small>
          <strong>{report.documents.length} файл(ов), язык: {LANG[report.lang] ?? report.lang}</strong>
          <div className="actions">
            <button type="button" className="primary" onClick={() => exportXlsx(report, reviews, checkId)
              .catch(e => setSaveError(`Экспорт не удался: ${(e as Error).message}`))}>Скачать XLSX</button>
            <button type="button" onClick={onReset}>Новая проверка</button>
          </div>
        </div>
        <div className={c.missing.length ? "bad" : "ok"}><small>Разделы</small><strong>{c.present.length} из {c.required.length}</strong></div>
        <div className={s.MISMATCH ? "bad" : "ok"}><small>Расхождения</small><strong>{s.MISMATCH}</strong></div>
        <div className={s.MISSING ? "bad" : "ok"}><small>Нет значения</small><strong>{s.MISSING}</strong></div>
        <div><small>Совпало проверок</small><strong>{s.MATCH}</strong></div>
        <div className={allBad.length && reviewed === allBad.length ? "ok" : ""}>
          <small>Проверено экспертом</small><strong>{reviewed} из {allBad.length}</strong>
        </div>
      </header>
      <main>
        <section className="panel list" aria-label="Результаты проверки">
          <div className="tabs" role="tablist">
            {tabs.map(t => (
              <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
                {t.label}{t.count !== undefined && <span className="count">{t.count}</span>}
              </button>
            ))}
          </div>
          <div className="tabpanel" role="tabpanel">
            {tab === "findings" && (
              <Findings
                report={report} bad={bad} ok={ok} filter={filter} onFilter={setFilter}
                matchesOpen={matchesOpen} onMatchesOpen={setMatchesOpen} current={current} onPick={f => pick(f, true)}
                reviewOf={reviewOf}
              />
            )}
            {tab === "tep" && <TepTables report={report} onPick={refs => setSelection({ refs })} />}
            {tab === "compl" && <Completeness report={report} />}
          </div>
        </section>
        <Viewer
          checkId={checkId} report={report} selection={selection}
          top={selection?.finding && (
            <ReviewBar
              review={reviewOf(selection.finding) ?? EMPTY} saving={saving} error={saveError}
              onChange={r => review(selection.finding!, r)}
            />
          )}
        />
      </main>
    </div>
  );
}
