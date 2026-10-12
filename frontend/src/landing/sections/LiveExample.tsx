import { useInView } from "motion/react";
import { lazy, Suspense, useContext, useRef } from "react";
import { Link } from "react-router";
import { LangContext } from "../i18n";
import Block from "./Block";

const DemoReport = lazy(() => import("../../demo/DemoReport")); // the platform's report: not in the landing entry

export default function LiveExample() {
  const { tl } = useContext(LangContext);
  const box = useRef<HTMLDivElement>(null);
  // pdf.js and the PDFs load when the block comes near, not with the first screen
  const near = useInView(box, { once: true, margin: "600px 0px" });
  return (
    <Block id="example" title={tl("example.title")} lead={tl("example.lead")}>
      <div ref={box} className="h-[640px] border border-line bg-sheet overflow-hidden">
        {near && <Suspense fallback={null}><DemoReport height="640px" embedded /></Suspense>}
      </div>
      <Link to="/demo" className="text-blue underline self-start">{tl("example.open")}</Link>
    </Block>
  );
}
