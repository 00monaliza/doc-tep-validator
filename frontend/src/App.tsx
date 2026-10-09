import { useEffect, useState } from "react";
import { startDemo, uploadFiles, waitForReport } from "./api";
import Intake from "./components/Intake";
import ReportView from "./components/ReportView";
import type { Report } from "./types";

const ID_RE = /^[0-9a-f]{32}$/;

type Status = { text: string; error?: boolean } | null;

export default function App() {
  const [check, setCheck] = useState<{ id: string; report: Report } | null>(null);
  const [status, setStatus] = useState<Status>(null);

  async function run(start: Promise<string> | string, slow = false) {
    setStatus({ text: slow ? "Распознаём сканы, это займёт до минуты…" : "Проверяем документы…" });
    try {
      const id = await start;
      const report = await waitForReport(id);
      history.replaceState(null, "", `?check=${id}`); // the link reopens this report
      setCheck({ id, report });
      setStatus(null);
    } catch (e) {
      setStatus({ text: (e as Error).message, error: true });
    }
  }

  useEffect(() => {
    const opened = new URLSearchParams(location.search).get("check");
    if (opened && ID_RE.test(opened)) run(opened);
  }, []);

  if (check) {
    return (
      <ReportView
        checkId={check.id}
        report={check.report}
        onReset={() => { history.replaceState(null, "", location.pathname); setCheck(null); }}
      />
    );
  }
  return (
    <Intake
      status={status}
      onFiles={files => run(uploadFiles(files))}
      onDemo={(lang, kind) => run(startDemo(lang, kind), kind === "scan")}
    />
  );
}
