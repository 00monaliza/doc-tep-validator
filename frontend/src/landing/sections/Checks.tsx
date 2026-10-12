import { useContext } from "react";
import Badge from "../../design/Badge";
import { t } from "../../lib/i18n";
import { CHECK_TYPES, SCAN_LIMITED } from "../content";
import { LangContext, type LKey } from "../i18n";
import Block from "./Block";

export default function Checks() {
  const { tl } = useContext(LangContext);
  return (
    <Block id="checks" title={tl("checks.title")} lead={tl("checks.lead")} tracing>
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {CHECK_TYPES.map(k => (
          <li key={k} className="bg-sheet border border-line p-4 flex flex-col gap-2">
            <span className="font-medium">{tl(`type.${k}` as LKey)}</span>
            {SCAN_LIMITED.includes(k) && <span><Badge kind="scan">{t("common.scan")}</Badge></span>}
          </li>
        ))}
      </ul>
      <p className="text-sm text-ink-2">{tl("checks.scanNote")}</p>
    </Block>
  );
}
