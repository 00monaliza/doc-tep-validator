import { useContext } from "react";
import { METRICS } from "../content";
import { LangContext } from "../i18n";
import Block from "./Block";

export default function Research() {
  const { tl } = useContext(LangContext);
  const { extraction: x, detectors: d, real: r } = METRICS;
  return (
    <Block id="research" title={tl("research.title")} lead={tl("research.lead")} tracing>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[[x, tl("research.extraction", { set: x.set })], [d, tl("research.detectors", { set: d.set })]].map(([m, label]) => {
          const mm = m as typeof x;
          return (
            <div key={label as string} className="bg-sheet border border-line p-5">
              <div className="flex gap-6">
                <span><span className="num text-3xl font-semibold text-blue block">{mm.ru}</span><span className="text-xs text-ink-2">RU</span></span>
                <span><span className="num text-3xl font-semibold text-blue block">{mm.kz}</span><span className="text-xs text-ink-2">KZ</span></span>
              </div>
              <p className="text-sm text-ink-2 mt-2">{label as string}</p>
            </div>
          );
        })}
      </div>
      <p className="bg-sheet border border-line p-5">
        <span className="num text-blue font-semibold">{r.tep}</span> · <span className="num text-blue font-semibold">{r.findings}</span> ·{" "}
        <span className="num font-semibold">{r.falsePositives}</span>
        <span className="block text-sm text-ink-2 mt-1">{tl("research.real", { tep: r.tep, findings: r.findings, fp: r.falsePositives })}</span>
      </p>
      <p className="text-ink-2 max-w-3xl">{tl("research.limits")}</p>
      <p className="text-xs text-ink-2">{tl("research.source")}</p>
    </Block>
  );
}
