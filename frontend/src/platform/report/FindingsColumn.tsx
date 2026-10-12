import { useEffect, useRef, useState } from "react";
import Badge from "../../design/Badge";
import Button from "../../design/Button";
import { SECTION, VERDICT, fieldName, fmt } from "../../lib/labels";
import type { Finding, Ref, Report, Review } from "../../lib/types";
import CompletenessTab from "./CompletenessTab";
import { comparedLabel, NO_FILTER, type Filter } from "./findings";
import { EXPERT } from "./ReviewBar";
import TepTab from "./TepTab";
import { t } from "../../lib/i18n";

const KIND = { MISMATCH: "mismatch", MISSING: "missing", MATCH: "match" } as const;
const NE = ({ c }: { c: string }) => <span className="text-pencil px-1.5">{c}</span>;
const SELECT = "min-h-[26px] border border-control rounded px-1.5 bg-sheet text-[13px] max-w-full";

/** The values of a finding in one line; one place, a pair, or three and more. */
function Values({ f }: { f: Finding }) {
  const [a, b] = f.refs;
  if (!b) return <>{SECTION[a.section]}: {fmt(a.value)}</>;
  if (f.refs.length > 2) {
    const uniq = [...new Set(f.refs.map(r => fmt(r.value)))];
    return <>{uniq.map((v, i) => <span key={i}>{i > 0 && <NE c="≠" />}{v}</span>)}</>;
  }
  if (f.verdict === "MISSING") return <>{SECTION[a.section]}: —<NE c="·" />{SECTION[b.section]}: {fmt(b.value)}</>;
  return <>{fmt(a.value)}<NE c={f.verdict === "MATCH" ? "=" : "≠"} />{fmt(b.value)}</>;
}

function Remark({ f, no, active, onPick, review }: {
  f: Finding; no: number; active: boolean; onPick: () => void; review?: Review;
}) {
  const rel = f.delta_rel != null && f.verdict === "MISMATCH" ? `, ${(f.delta_rel * 100).toFixed(1).replace(".", ",")} %` : "";
  return (
    <li>
      <button type="button" aria-current={active || undefined} onClick={onPick}
        className="w-full text-left grid grid-cols-[28px_1fr] gap-x-2 px-3 py-2.5 border-b border-line hover:bg-paper aria-[current=true]:bg-pencil-wash aria-[current=true]:shadow-[inset_3px_0_0_var(--pencil)]">
        <span className="num text-[13px] text-ink-2 pt-0.5">{no}</span>
        <span className="min-w-0 flex flex-col gap-0.5">
          <span className="flex flex-wrap items-center gap-1">
            <Badge kind={KIND[f.verdict]}>{VERDICT[f.verdict]}</Badge>
            <span className="font-medium">{fieldName(f.field)}</span>
            {f.low_confidence && <Badge kind="scan">{t("common.scan")}</Badge>}
            {f.needs_expert && <Badge kind="expert">{t("common.expert")}</Badge>}
            {review?.verdict && <Badge kind={review.verdict}>{EXPERT[review.verdict]}</Badge>}
          </span>
          {f.object_name && <span className="font-cond text-sm text-blue">{f.object_name}</span>}
          <span className="num font-semibold">{<Values f={f} />}</span>
          <span className="text-[13px] text-ink-2">{comparedLabel(f)}{rel}</span>
          {review?.comment && <span className="text-[13px] text-ink-2 italic">{t("report.expertComment", { text: review.comment })}</span>}
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
  const active = filter.building || filter.compared || filter.flag || filter.review;
  const set = (patch: Partial<Filter>) => onFilter({ ...filter, ...patch });
  return (
    <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-line">
      {buildings.length > 1 && (
        <select aria-label={t("filter.building")} className={SELECT} value={filter.building} onChange={e => set({ building: e.target.value })}>
          <option value="">{t("filter.allBuildings")}</option>{buildings.map(b => <option key={b}>{b}</option>)}
        </select>
      )}
      {compared.length > 1 && (
        <select aria-label={t("filter.compared")} className={SELECT} value={filter.compared} onChange={e => set({ compared: e.target.value })}>
          <option value="">{t("filter.allCompared")}</option>{compared.map(c => <option key={c}>{c}</option>)}
        </select>
      )}
      {hasFlags && (
        <select aria-label={t("filter.flag")} className={SELECT} value={filter.flag} onChange={e => set({ flag: e.target.value as Filter["flag"] })}>
          <option value="">{t("filter.anyFlag")}</option><option value="expert">{t("filter.expertOnly")}</option><option value="noscan">{t("filter.noScans")}</option>
        </select>
      )}
      <select aria-label={t("filter.verdict")} className={SELECT} value={filter.review} onChange={e => set({ review: e.target.value as Filter["review"] })}>
        <option value="">{t("filter.allVerdicts")}</option><option value="none">{t("filter.noVerdict")}</option>
        <option value="confirmed">{t("filter.confirmed")}</option><option value="false_positive">{t("filter.false")}</option>
      </select>
      {active && (
        <>
          <span className="text-xs text-ink-2">{t("filter.shown", { n: shown, total: all.length })}</span>
          <Button size="sm" variant="ghost" onClick={() => onFilter(NO_FILTER)}>{t("filter.reset")}</Button>
        </>
      )}
    </div>
  );
}

type Tab = "findings" | "tep" | "completeness";

interface Props {
  report: Report;
  bad: Finding[]; ok: Finding[]; // already filtered
  filter: Filter; onFilter: (f: Filter) => void;
  matchesOpen: boolean; onMatchesOpen: (open: boolean) => void;
  current: Finding | null; onPick: (f: Finding) => void;
  reviewOf: (f: Finding) => Review | undefined;
  onPickRefs: (refs: Ref[]) => void;
}

/** Left column of the report: findings with filters, the extracted TEP, completeness. */
export default function FindingsColumn(
  { report, bad, ok, filter, onFilter, matchesOpen, onMatchesOpen, current, onPick, reviewOf, onPickRefs }: Props,
) {
  const [tab, setTab] = useState<Tab>("findings");
  const listRef = useRef<HTMLDivElement>(null);
  // scroll the column only: scrollIntoView would also scroll the window, and the report may sit inside the landing
  useEffect(() => {
    const box = listRef.current?.parentElement;
    const el = listRef.current?.querySelector<HTMLElement>('[aria-current="true"]');
    if (!box || !el) return;
    const top = el.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop;
    if (top < box.scrollTop) box.scrollTop = top;
    else if (top + el.offsetHeight > box.scrollTop + box.clientHeight) box.scrollTop = top + el.offsetHeight - box.clientHeight;
  }, [current, matchesOpen]);
  const c = report.completeness;
  const tabs: [Tab, string, string][] = [
    ["findings", t("report.tab.findings"), String(bad.length)], ["tep", t("report.tab.tep"), ""],
    ["completeness", t("report.tab.completeness"), c.missing.length ? `−${c.missing.length}` : ""],
  ];

  return (
    <div ref={listRef} className="flex flex-col min-h-0">
      <div role="tablist" className="flex border-b border-line sticky top-0 bg-sheet z-10">
        {tabs.map(([id, label, count]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
            className="flex-1 min-h-9 font-cond text-sm text-ink-2 aria-selected:text-ink aria-selected:shadow-[inset_0_-3px_0_var(--ink)]">
            {label}{count && <span className="ml-1 font-semibold">{count}</span>}
          </button>
        ))}
      </div>
      {tab === "findings" && (
        <>
          <FilterBar all={report.findings} filter={filter} onFilter={onFilter} shown={bad.length + ok.length} />
          {(report.warnings ?? []).map((w, i) => (
            <div key={i} className="border-l-[3px] border-amber bg-amber-wash px-3 py-2 text-sm m-3">{w}</div>
          ))}
          {bad.length ? (
            <ol>{bad.map((f, i) => <Remark key={i} f={f} no={i + 1} active={f === current} onPick={() => onPick(f)} review={reviewOf(f)} />)}</ol>
          ) : (
            <p className="p-4 text-ink-2">
              {filter === NO_FILTER ? t("report.none") : t("report.filtered.none")}
            </p>
          )}
          {ok.length > 0 && (
            <details open={matchesOpen} onToggle={e => onMatchesOpen((e.target as HTMLDetailsElement).open)}>
              <summary className="px-3 py-2.5 cursor-pointer font-cond text-sm text-ink-2">{t("report.matches", { n: ok.length })}</summary>
              <ol>{ok.map((f, i) => (
                <Remark key={i} f={f} no={bad.length + i + 1} active={f === current} onPick={() => onPick(f)} review={reviewOf(f)} />
              ))}</ol>
            </details>
          )}
        </>
      )}
      {tab === "tep" && <TepTab report={report} onPick={onPickRefs} />}
      {tab === "completeness" && <CompletenessTab report={report} />}
    </div>
  );
}
