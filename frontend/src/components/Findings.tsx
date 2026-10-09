import { useEffect, useRef } from "react";
import { SECTION, TYPE, VERDICT, fieldName, fmt } from "../labels";
import type { Finding, Report } from "../types";

/** What a finding compares: a section pair, or the check type when both places are in one section. */
export function comparedLabel(f: Finding): string {
  const [a, b] = f.refs;
  return !b || a.section === b.section ? (TYPE[f.type] ?? f.type) : `${SECTION[a.section]} ↔ ${SECTION[b.section]}`;
}

export interface Filter { building: string; compared: string; flag: "" | "expert" | "noscan" }
export const NO_FILTER: Filter = { building: "", compared: "", flag: "" };

export function applyFilter(list: Finding[], f: Filter): Finding[] {
  return list.filter(x =>
    (!f.building || (x.object_name ?? "") === f.building)
    && (!f.compared || comparedLabel(x) === f.compared)
    && (f.flag !== "expert" || x.needs_expert)
    && (f.flag !== "noscan" || !x.low_confidence));
}

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
          <div className="meta">{comparedLabel(f)}{rel}</div>
          {f.notes.map((n, i) => <div key={i} className="meta">{n}</div>)}
        </span>
      </button>
    </li>
  );
}

function FilterBar({ all, filter, onFilter, shown }: {
  all: Finding[]; filter: Filter; onFilter: (f: Filter) => void; shown: number;
}) {
  const buildings = [...new Set(all.map(f => f.object_name).filter(Boolean) as string[])];
  const compared = [...new Set(all.map(comparedLabel))];
  const hasFlags = all.some(f => f.needs_expert || f.low_confidence);
  const active = filter.building || filter.compared || filter.flag;
  const set = (patch: Partial<Filter>) => onFilter({ ...filter, ...patch });
  return (
    <div className="filters">
      {buildings.length > 1 && (
        <select aria-label="Здание" value={filter.building} onChange={e => set({ building: e.target.value })}>
          <option value="">Все здания</option>
          {buildings.map(b => <option key={b}>{b}</option>)}
        </select>
      )}
      {compared.length > 1 && (
        <select aria-label="Что сверяется" value={filter.compared} onChange={e => set({ compared: e.target.value })}>
          <option value="">Все проверки</option>
          {compared.map(c => <option key={c}>{c}</option>)}
        </select>
      )}
      {hasFlags && (
        <select aria-label="Признак" value={filter.flag} onChange={e => set({ flag: e.target.value as Filter["flag"] })}>
          <option value="">Любые</option>
          <option value="expert">Только «эксперту»</option>
          <option value="noscan">Без сканов</option>
        </select>
      )}
      {active && (
        <>
          <span className="shown">показано {shown} из {all.length}</span>
          <button type="button" className="link" onClick={() => onFilter(NO_FILTER)}>сбросить</button>
        </>
      )}
    </div>
  );
}

interface Props {
  report: Report;
  bad: Finding[]; ok: Finding[]; // already filtered
  filter: Filter; onFilter: (f: Filter) => void;
  matchesOpen: boolean; onMatchesOpen: (open: boolean) => void;
  current: Finding | null; onPick: (f: Finding) => void;
}

export default function Findings({ report, bad, ok, filter, onFilter, matchesOpen, onMatchesOpen, current, onPick }: Props) {
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    listRef.current?.querySelector('[aria-current="true"]')?.scrollIntoView({ block: "nearest" });
  }, [current, matchesOpen]);

  return (
    <div ref={listRef}>
      <FilterBar all={report.findings} filter={filter} onFilter={onFilter} shown={bad.length + ok.length} />
      {(report.warnings ?? []).map((w, i) => <div key={i} className="note">{w}</div>)}
      {bad.length ? (
        <ol className="register">
          {bad.map((f, i) => <Remark key={i} f={f} no={i + 1} active={f === current} onPick={() => onPick(f)} />)}
        </ol>
      ) : (
        <div className="empty">
          {filter === NO_FILTER ? "Расхождений между разделами не найдено." : "Под фильтр не попало ни одного расхождения."}
        </div>
      )}
      {ok.length > 0 && (
        <details className="matches" open={matchesOpen}
          onToggle={e => onMatchesOpen((e.target as HTMLDetailsElement).open)}>
          <summary>Совпавшие проверки: {ok.length}</summary>
          <ol className="register">
            {ok.map((f, i) => (
              <Remark key={i} f={f} no={bad.length + i + 1} active={f === current} onPick={() => onPick(f)} />
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}
