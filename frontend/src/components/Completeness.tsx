import { SECTION, SECTION_FULL } from "../labels";
import type { DocumentInfo, Report } from "../types";

export default function Completeness({ report }: { report: Report }) {
  const c = report.completeness;
  const byS: Record<string, DocumentInfo> = Object.fromEntries(
    report.documents.filter(d => d.section).map(d => [d.section, d]),
  );
  return (
    <>
      <ul className="sheet-list">
        {c.required.map(s => (
          <li key={s}>
            <span className="code">{SECTION[s]}</span>
            <span>
              {SECTION_FULL[s]}
              {byS[s] && <><br /><small>{byS[s].file}{byS[s].ocr ? " (скан)" : ""}</small></>}
            </span>
            {byS[s] ? <span className="present">загружен</span> : <span className="absent">нет в пакете</span>}
          </li>
        ))}
      </ul>
      {c.unrecognised.map(f => <div key={f} className="note">{f}: раздел не определён.</div>)}
      {c.duplicates.map(f => <div key={f} className="note">{f}: второй документ того же раздела не учитывался.</div>)}
    </>
  );
}
