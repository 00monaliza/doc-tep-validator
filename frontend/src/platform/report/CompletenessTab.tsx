import { SECTION, SECTION_FULL } from "../../lib/labels";
import type { DocumentInfo, Report } from "../../lib/types";
import { t } from "../../lib/i18n";

export default function Completeness({ report }: { report: Report }) {
  const c = report.completeness;
  const byS: Record<string, DocumentInfo> = Object.fromEntries(
    report.documents.filter(d => d.section).map(d => [d.section, d]),
  );
  return (
    <>
      <ul className="px-3 py-2">
        {c.required.map(s => (
          <li key={s} className="grid grid-cols-[56px_1fr_auto] gap-2.5 py-2 border-b border-line items-baseline">
            <span className="font-cond font-semibold">{SECTION[s]}</span>
            <span>
              {SECTION_FULL[s]}
              {byS[s] && <><br /><small>{byS[s].file}{byS[s].ocr ? t("completeness.scan") : ""}</small></>}
            </span>
            {byS[s] ? <span className="text-blue font-cond text-sm">{t("completeness.present")}</span> : <span className="text-pencil font-cond text-sm">{t("completeness.absent")}</span>}
          </li>
        ))}
      </ul>
      {c.unrecognised.map(f => <div key={f} className="border-l-[3px] border-amber bg-amber-wash px-3 py-2 text-sm m-3">{t("completeness.unrecognised", { file: f })}</div>)}
      {c.duplicates.map(f => <div key={f} className="border-l-[3px] border-amber bg-amber-wash px-3 py-2 text-sm m-3">{t("completeness.duplicate", { file: f })}</div>)}
    </>
  );
}
