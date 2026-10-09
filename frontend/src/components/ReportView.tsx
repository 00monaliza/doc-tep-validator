import { useEffect, useMemo, useState } from "react";
import { LANG } from "../labels";
import type { Finding, Ref, Report } from "../types";
import Completeness from "./Completeness";
import Findings, { NO_FILTER, applyFilter, type Filter } from "./Findings";
import TepTables from "./TepTables";
import Viewer from "./Viewer";

type Tab = "findings" | "tep" | "compl";

interface Props { checkId: string; report: Report; onReset: () => void }

export default function ReportView({ checkId, report, onReset }: Props) {
  const [filter, setFilter] = useState<Filter>(NO_FILTER);
  const bad = useMemo(() => applyFilter(report.findings.filter(f => f.verdict !== "MATCH"), filter), [report, filter]);
  const ok = useMemo(() => applyFilter(report.findings.filter(f => f.verdict === "MATCH"), filter), [report, filter]);
  const [tab, setTab] = useState<Tab>("findings");
  const [matchesOpen, setMatchesOpen] = useState(false);
  const [current, setCurrent] = useState<Finding | null>(bad[0] ?? null);
  const [selection, setSelection] = useState<{ refs: Ref[]; finding?: Finding } | null>(
    current ? { refs: current.refs, finding: current } : null,
  );
  const c = report.completeness;
  const s = report.summary;

  const pick = (f: Finding) => {
    setCurrent(f);
    setSelection({ refs: f.refs, finding: f });
    if (ok.includes(f)) setMatchesOpen(true);
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
          <small>Проверка пакета · <button className="link" onClick={onReset}>новая проверка</button></small>
          <strong>{report.documents.length} файл(ов), язык: {LANG[report.lang] ?? report.lang}</strong>
        </div>
        <div className={c.missing.length ? "bad" : "ok"}><small>Разделы</small><strong>{c.present.length} из {c.required.length}</strong></div>
        <div className={s.MISMATCH ? "bad" : "ok"}><small>Расхождения</small><strong>{s.MISMATCH}</strong></div>
        <div className={s.MISSING ? "bad" : "ok"}><small>Нет значения</small><strong>{s.MISSING}</strong></div>
        <div><small>Совпало проверок</small><strong>{s.MATCH}</strong></div>
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
                matchesOpen={matchesOpen} onMatchesOpen={setMatchesOpen} current={current} onPick={pick}
              />
            )}
            {tab === "tep" && <TepTables report={report} onPick={refs => setSelection({ refs })} />}
            {tab === "compl" && <Completeness report={report} />}
          </div>
        </section>
        <Viewer checkId={checkId} report={report} selection={selection} />
      </main>
    </div>
  );
}
