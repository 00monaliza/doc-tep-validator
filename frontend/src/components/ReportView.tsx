import { useMemo, useState } from "react";
import { LANG } from "../labels";
import type { Finding, Ref, Report } from "../types";
import Completeness from "./Completeness";
import Findings from "./Findings";
import TepTables from "./TepTables";
import Viewer from "./Viewer";

type Tab = "findings" | "tep" | "compl";

interface Props { checkId: string; report: Report; onReset: () => void }

export default function ReportView({ checkId, report, onReset }: Props) {
  const bad = useMemo(() => report.findings.filter(f => f.verdict !== "MATCH"), [report]);
  const ok = useMemo(() => report.findings.filter(f => f.verdict === "MATCH"), [report]);
  const [tab, setTab] = useState<Tab>("findings");
  const [current, setCurrent] = useState<Finding | null>(bad[0] ?? ok[0] ?? null);
  const [selection, setSelection] = useState<{ refs: Ref[]; finding?: Finding } | null>(
    current ? { refs: current.refs, finding: current } : null,
  );
  const c = report.completeness;
  const s = report.summary;

  const pick = (f: Finding) => { setCurrent(f); setSelection({ refs: f.refs, finding: f }); };

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
            {tab === "findings" && <Findings report={report} bad={bad} ok={ok} current={current} onPick={pick} />}
            {tab === "tep" && <TepTables report={report} onPick={refs => setSelection({ refs })} />}
            {tab === "compl" && <Completeness report={report} />}
          </div>
        </section>
        <Viewer checkId={checkId} report={report} selection={selection} />
      </main>
    </div>
  );
}
