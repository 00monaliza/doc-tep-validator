import { useContext } from "react";
import { LangContext, type LKey } from "../i18n";

export default function HowItWorks() {
  const { tl } = useContext(LangContext);
  return (
    <section id="how" aria-labelledby="how-title" className="px-4 md:px-6 py-16 flex flex-col gap-6">
      <h2 id="how-title" className="text-2xl md:text-4xl font-semibold leading-tight">{tl("how.title")}</h2>
      <ol className="flex flex-col gap-6">
        {[1, 2, 3].map(n => (
          <li key={n} className="grid grid-cols-[48px_1fr] gap-3 min-h-[28vh] md:min-h-[40vh] content-start">
            <span className="num text-3xl font-semibold text-blue">{n}</span>
            <span><b className="block text-lg">{tl(`how.step${n}.title` as LKey)}</b><span className="text-ink-2">{tl(`how.step${n}.text` as LKey)}</span></span>
          </li>
        ))}
      </ol>
    </section>
  );
}
