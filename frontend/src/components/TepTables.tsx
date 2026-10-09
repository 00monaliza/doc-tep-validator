import { Fragment } from "react";
import { SECTIONS, SECTION_FULL, fieldName } from "../labels";
import type { Ref, Report, TepEntry } from "../types";

export default function TepTables({ report, onPick }: { report: Report; onPick: (refs: Ref[]) => void }) {
  const objects = report.objects ?? {};
  const tables = SECTIONS.filter(s => report.tep[s]).map(s => {
    const all = Object.entries(report.tep[s]!);
    const entries = all.filter(([k]) => !k.startsWith("room."));
    const rooms = all.length - entries.length;
    const groups: Record<string, [string, TepEntry][]> = {};
    for (const [k, e] of entries) (groups[e.object ?? ""] ??= []).push([k, e]);
    const keys = Object.keys(groups);
    const multi = keys.length > 1 || (keys[0] ?? "") !== "";

    return (
      <table key={s} className="grid">
        <caption>{SECTION_FULL[s]}{rooms ? ` · помещений в экспликации: ${rooms}` : ""}</caption>
        <thead><tr><th>Показатель</th><th className="num">Значение</th><th>Где</th></tr></thead>
        <tbody>
          {Object.entries(groups).map(([obj, rows]) => (
            <Fragment key={obj}>
              {multi && (
                <tr className="group"><td colSpan={3}>
                  {objects[obj] ?? (obj || "Без привязки к зданию")}
                  {obj && obj === report.pz_building ? " · сверяется с АР/КР/сметой" : ""}
                </td></tr>
              )}
              {rows.map(([k, e]) => {
                const go = () => onPick([{ ...e, value: e.value ?? e.raw, section: s }]);
                return (
                  <tr key={k} className="clickable" tabIndex={0} onClick={go} onKeyDown={ev => ev.key === "Enter" && go()}>
                    <td>{fieldName(k.includes("/") ? k.split("/")[1] : k)}</td>
                    <td className="num">{e.raw}</td>
                    <td>{e.page ? `стр. ${e.page}` : "—"}</td>
                  </tr>
                );
              })}
            </Fragment>
          ))}
        </tbody>
      </table>
    );
  });
  return tables.length ? <>{tables}</> : <div className="empty">Показатели не найдены.</div>;
}
