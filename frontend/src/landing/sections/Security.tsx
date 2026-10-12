import { useContext } from "react";
import { FACTS } from "../content";
import { LangContext } from "../i18n";
import Block from "./Block";

export default function Security() {
  const { tl } = useContext(LangContext);
  const items = [tl("security.invite"), tl("security.own"), tl("security.retention", { n: FACTS.retentionDays }), tl("security.noLlm")];
  return (
    <Block id="security" title={tl("security.title")}>
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {items.map(text => (
          <li key={text} className="flex gap-3 items-start bg-sheet border border-line p-4">
            <span aria-hidden="true" className="text-green font-semibold">✓</span><span>{text}</span>
          </li>
        ))}
      </ul>
    </Block>
  );
}
