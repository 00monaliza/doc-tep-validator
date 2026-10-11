import { Fragment } from "react";
import { SECTIONS, SECTION_FULL, fieldName } from "../../lib/labels";
import type { Ref, Report, TepEntry } from "../../lib/types";
import { t } from "../../lib/i18n";

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
      <table key={s} className="w-full border-collapse text-sm mb-2">
        <caption className="text-left px-3 pt-3 pb-1 font-cond font-semibold">{SECTION_FULL[s]}{rooms ? t("tep.rooms", { n: rooms }) : ""}</caption>
        <thead><tr className="text-left font-cond text-[11px] uppercase tracking-wide text-ink-2"><th className="px-3 py-1.5">{t("tep.col.field")}</th><th className="px-3 py-1.5 text-right">{t("tep.col.value")}</th><th className="px-3 py-1.5">{t("tep.col.where")}</th></tr></thead>
        <tbody>
          {Object.entries(groups).map(([obj, rows]) => (
            <Fragment key={obj}>
              {multi && (
                <tr className="bg-blue-wash text-blue font-cond font-semibold"><td colSpan={3} className="px-3 py-1">
                  {objects[obj] ?? (obj || t("tep.noBuilding"))}
                  {obj && obj === report.pz_building ? t("tep.pzBuilding") : ""}
                </td></tr>
              )}
              {rows.map(([k, e]) => {
                const go = () => onPick([{ ...e, value: e.value ?? e.raw, section: s }]);
                return (
                  <tr key={k} className="border-t border-line cursor-pointer hover:bg-paper" tabIndex={0} onClick={go} onKeyDown={ev => ev.key === "Enter" && go()}>
                    <td className="px-3 py-1.5">{fieldName(k.includes("/") ? k.split("/")[1] : k)}</td>
                    <td className="px-3 py-1.5 num text-right whitespace-nowrap">{e.raw}</td>
                    <td className="px-3 py-1.5 text-ink-2">{e.page ? t("common.page", { page: e.page }) : "—"}</td>
                  </tr>
                );
              })}
            </Fragment>
          ))}
        </tbody>
      </table>
    );
  });
  return tables.length ? <>{tables}</> : <p className="p-4 text-ink-2">{t("tep.none")}</p>;
}
