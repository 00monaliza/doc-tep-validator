import { useContext } from "react";
import { LangContext } from "../i18n";
import Block from "./Block";

export default function AccessRequest() {
  const { tl } = useContext(LangContext);
  return <Block id="access" title={tl("access.title")} lead={tl("access.lead")} tracing />;
}
