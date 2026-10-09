import { useEffect, useState } from "react";
import { startDemo, startUploaded, uploadFiles, waitForCheck } from "./api";
import FileReview from "./components/FileReview";
import Intake from "./components/Intake";
import ReportView from "./components/ReportView";
import type { Choice, Report, Reviews, UploadedFile } from "./types";

const ID_RE = /^[0-9a-f]{32}$/;

type Status = { text: string; error?: boolean } | null;
type Screen =
  | { kind: "intake" }
  | { kind: "review"; id: string; files: Record<string, UploadedFile> }
  | { kind: "report"; id: string; report: Report; reviews: Reviews };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ kind: "intake" });
  const [status, setStatus] = useState<Status>(null);

  async function follow(start: Promise<string> | string, slow = false) {
    setStatus({ text: slow ? "Распознаём сканы, это займёт до минуты…" : "Проверяем документы…" });
    try {
      const id = await start;
      history.replaceState(null, "", `?check=${id}`); // the link reopens this check
      const outcome = await waitForCheck(id);
      setScreen(outcome.kind === "report"
        ? { kind: "report", id, report: outcome.report, reviews: outcome.reviews }
        : { kind: "review", id, files: outcome.files });
      setStatus(null);
    } catch (e) {
      setStatus({ text: (e as Error).message, error: true });
    }
  }

  async function upload(files: FileList) {
    setStatus({ text: "Загружаем файлы и определяем разделы…" });
    try {
      const { id, files: uploaded } = await uploadFiles(files);
      history.replaceState(null, "", `?check=${id}`);
      setScreen({ kind: "review", id, files: uploaded });
      setStatus(null);
    } catch (e) {
      setStatus({ text: (e as Error).message, error: true });
    }
  }

  const reset = () => { history.replaceState(null, "", location.pathname); setScreen({ kind: "intake" }); setStatus(null); };

  useEffect(() => {
    const opened = new URLSearchParams(location.search).get("check");
    if (opened && ID_RE.test(opened)) follow(opened);
  }, []);

  if (screen.kind === "report") {
    return <ReportView checkId={screen.id} report={screen.report} initialReviews={screen.reviews} onReset={reset} />;
  }
  if (screen.kind === "review") {
    const id = screen.id;
    const scans = Object.values(screen.files).some(f => f.how === "scan");
    return (
      <FileReview
        files={screen.files} status={status} busy={status != null && !status.error} onCancel={reset}
        onStart={(choices: Record<string, Choice>) => follow(startUploaded(id, choices), scans)}
      />
    );
  }
  return (
    <Intake
      status={status}
      onFiles={upload}
      onDemo={(lang, kind) => follow(startDemo(lang, kind), kind === "scan")}
    />
  );
}
