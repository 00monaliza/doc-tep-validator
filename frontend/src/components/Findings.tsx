import { SECTION, TYPE, VERDICT, fieldName, fmt } from "../labels";
import type { Finding, Report } from "../types";

function Values({ f }: { f: Finding }) {
  const [a, b] = f.refs;
  if (f.refs.length > 2) {
    const uniq = [...new Set(f.refs.map(r => fmt(r.value)))];
    return <>{uniq.map((v, i) => <span key={i}>{i > 0 && <span className="ne">≠</span>}{v}</span>)}</>;
  }
  if (f.verdict === "MISSING")
    return <>{SECTION[a.section]}: —<span className="ne">·</span>{SECTION[b.section]}: {fmt(b.value)}</>;
  return <>{fmt(a.value)}<span className="ne">{f.verdict === "MATCH" ? "=" : "≠"}</span>{fmt(b.value)}</>;
}

function Remark({ f, no, active, onPick }: { f: Finding; no: number; active: boolean; onPick: () => void }) {
  const [a, b] = f.refs;
  const rel = f.delta_rel != null && f.verdict === "MISMATCH"
    ? `, ${(f.delta_rel * 100).toFixed(1).replace(".", ",")} %` : "";
  return (
    <li>
      <button className="remark" aria-current={active || undefined} onClick={onPick}>
        <span className="no">{no}</span>
        <span>
          <span className={`verdict v-${f.verdict}`}>{VERDICT[f.verdict]}</span>
          <span className="what">{fieldName(f.field)}</span>
          {f.low_confidence && <> <span className="verdict v-MISSING">скан</span></>}
          {f.needs_expert && <> <span className="verdict v-MISSING">эксперту</span></>}
          {f.object_name && <div className="obj">{f.object_name}</div>}
          <div className="values"><Values f={f} /></div>
          <div className="meta">
            {a.section === b?.section ? (TYPE[f.type] ?? f.type) : `${SECTION[a.section]} ↔ ${SECTION[b?.section]}`}{rel}
          </div>
          {f.notes.map((n, i) => <div key={i} className="meta">{n}</div>)}
        </span>
      </button>
    </li>
  );
}

interface Props {
  report: Report; bad: Finding[]; ok: Finding[];
  current: Finding | null; onPick: (f: Finding) => void;
}

export default function Findings({ report, bad, ok, current, onPick }: Props) {
  return (
    <>
      {(report.warnings ?? []).map((w, i) => <div key={i} className="note">{w}</div>)}
      {bad.length ? (
        <ol className="register">
          {bad.map((f, i) => <Remark key={i} f={f} no={i + 1} active={f === current} onPick={() => onPick(f)} />)}
        </ol>
      ) : <div className="empty">Расхождений между разделами не найдено.</div>}
      {ok.length > 0 && (
        <details className="matches">
          <summary>Совпавшие проверки: {ok.length}</summary>
          <ol className="register">
            {ok.map((f, i) => (
              <Remark key={i} f={f} no={bad.length + i + 1} active={f === current} onPick={() => onPick(f)} />
            ))}
          </ol>
        </details>
      )}
    </>
  );
}
