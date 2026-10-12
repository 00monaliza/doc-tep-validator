import { useContext } from "react";
import { SAMPLE_AREA } from "../content";
import { LangContext } from "../i18n";
import Block from "./Block";

/** The same TEP sentence in both languages, the value marked with the expert's pencil. */
function Quote({ text, lang }: { text: string; lang: string }) {
  const [before, after] = text.split("{value}");
  return (
    <blockquote lang={lang} className="bg-sheet border-l-4 border-blue px-4 py-3 text-lg">
      {before}<span className="num text-pencil font-semibold">{SAMPLE_AREA}</span>{after}
    </blockquote>
  );
}

export default function Languages() {
  const { tl } = useContext(LangContext);
  const raw = (k: "langs.ru" | "langs.kz") => tl(k, { value: "{value}" });
  return (
    <Block id="languages" title={tl("langs.title")} lead={tl("langs.lead")}>
      <Quote text={raw("langs.ru")} lang="ru" />
      <Quote text={raw("langs.kz")} lang="kk" />
    </Block>
  );
}
