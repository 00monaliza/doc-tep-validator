import { useEffect, useState } from "react";
import EmptyState from "../design/EmptyState";
import { t } from "../lib/i18n";
import type { Report } from "../lib/types";
import { staticFileSource, FileSourceContext } from "../platform/report/fileSource";
import { ReportBody } from "../platform/report/ReportPage";
import { loadDemo } from "./loadDemo";

const DEMO = "0".repeat(32); // the demo has no check id; the report only uses it as a cache key
const source = staticFileSource("/demo-data");

/** The real report on the bundled sample: no login, no API; verdicts stay in the page. */
export default function DemoReport({ height = "100%", embedded = false }: { height?: string; embedded?: boolean }) {
  const [data, setData] = useState<{ report: Report; title: string } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    // a cancelled load must not replace the report: the open finding would then belong to another object
    let alive = true;
    loadDemo().then(d => alive && setData(d), e => alive && setError((e as Error).message));
    return () => { alive = false; };
  }, []);
  if (error) return <EmptyState title={error} />;
  if (!data) return <p className="p-6 text-ink-2">{t("common.loading")}</p>;
  return (
    <FileSourceContext.Provider value={source}>
      <div style={{ height }} className="flex flex-col min-h-0 overflow-auto bg-tracing">
        <ReportBody checkId={DEMO} report={data.report} title={data.title} initial={{}} onSave={async () => {}} titleLevel={embedded ? 3 : 1} keys={!embedded} />
      </div>
    </FileSourceContext.Provider>
  );
}
