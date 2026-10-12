import { lazy, Suspense, useContext } from "react";
import { Link } from "react-router";
import { LangContext } from "../i18n";
import Block from "./Block";

const DemoReport = lazy(() => import("../../demo/DemoReport")); // the platform's report: not in the landing entry

export default function LiveExample() {
  const { tl } = useContext(LangContext);
  return (
    <Block id="example" title={tl("example.title")} lead={tl("example.lead")}>
      <div className="h-[640px] border border-line bg-sheet overflow-hidden">
        <Suspense fallback={null}><DemoReport height="640px" /></Suspense>
      </div>
      <Link to="/demo" className="text-blue underline self-start">{tl("example.open")}</Link>
    </Block>
  );
}
