import { useContext } from "react";
import { FACTS } from "../content";
import { LangContext } from "../i18n";

export default function Problem() {
  const { tl } = useContext(LangContext);
  const items: [number, string][] = [[FACTS.sections, tl("problem.sections")], [FACTS.tepFields, tl("problem.fields")], [FACTS.checkTypes, tl("problem.types")]];
  return (
    <section id="problem" aria-labelledby="problem-title" className="px-4 md:px-6 py-16 flex flex-col gap-6">
      <h2 id="problem-title" className="text-2xl md:text-4xl font-semibold leading-tight">{tl("problem.title")}</h2>
      <p className="text-ink-2 max-w-xl">{tl("problem.lead")}</p>
      <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {items.map(([n, label]) => (
          <div key={label} className="bg-sheet border border-line p-4">
            <dt className="sr-only">{label}</dt>
            <dd><span className="num text-4xl font-semibold text-blue block">{n}</span><span className="text-sm text-ink-2">{label}</span></dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
