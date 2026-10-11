import { useEffect, useReducer, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router";
import Button from "../../design/Button";
import { getCheck, startUploaded, uploadFiles } from "../../lib/api";
import { t } from "../../lib/i18n";
import type { UploadedFile } from "../../lib/types";
import FileReview from "../report/FileReview";
import Stepper from "./Stepper";

export type WizardState =
  | { step: "files" }
  | { step: "uploading"; sent: number; total: number }
  | { step: "sections"; id: string; files: Record<string, UploadedFile> }
  | { step: "running"; id: string }
  | { step: "failed"; message: string };
export type WizardEvent =
  | { type: "upload"; total: number } | { type: "progress"; sent: number }
  | { type: "uploaded"; id: string; files: Record<string, UploadedFile> }
  | { type: "start" } | { type: "fail"; message: string } | { type: "reset" };

export function reduceWizard(s: WizardState, e: WizardEvent): WizardState {
  switch (e.type) {
    case "upload": return { step: "uploading", sent: 0, total: e.total };
    case "progress": return s.step === "uploading" ? { ...s, sent: e.sent } : s;
    case "uploaded": return { step: "sections", id: e.id, files: e.files };
    case "start": return s.step === "sections" ? { step: "running", id: s.id } : s;
    case "fail": return { step: "failed", message: e.message };
    case "reset": return { step: "files" };
  }
}

const mb = (b: number) => (b / 2 ** 20).toLocaleString("ru-RU", { maximumFractionDigits: 1 });

export default function NewCheckPage() {
  const [s, dispatch] = useReducer(reduceWizard, { step: "files" });
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {  // a link to an unfinished wizard resumes at "sections"
    const id = params.get("id");
    if (!id) return;
    getCheck(id).then(c => c.status === "uploaded"
      ? dispatch({ type: "uploaded", id, files: c.files })
      : nav(`/app/checks/${id}`, { replace: true }), e => dispatch({ type: "fail", message: (e as Error).message }));
  }, []);

  const upload = async (files: FileList) => {
    if (!files.length) return;
    dispatch({ type: "upload", total: [...files].reduce((n, f) => n + f.size, 0) });
    try {
      const r = await uploadFiles(files, sent => dispatch({ type: "progress", sent }));
      setParams({ id: r.id }, { replace: true });
      dispatch({ type: "uploaded", id: r.id, files: r.files });
    } catch (e) { dispatch({ type: "fail", message: (e as Error).message }); }
  };

  const current = s.step === "sections" ? 1 : s.step === "running" ? 2 : 0;
  return (
    <section className="p-6 flex flex-col gap-5 max-w-4xl">
      <h1 className="text-2xl font-semibold">{t("nav.new")}</h1>
      <Stepper current={current} />
      {(s.step === "files" || s.step === "failed") && (
        <label className="block border-2 border-dashed border-control bg-sheet p-10 text-center cursor-pointer"
          onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); upload(e.dataTransfer.files); }}>
          <span className="block font-semibold">{t("new.drop")}</span>
          <span className="text-sm text-ink-2">{t("new.drop.hint")}</span>
          <input ref={input} type="file" multiple accept=".pdf,.docx" className="sr-only" onChange={e => e.target.files && upload(e.target.files)} />
        </label>
      )}
      {s.step === "failed" && <p role="alert" className="text-pencil">{s.message}</p>}
      {s.step === "uploading" && (
        <div role="status" className="flex flex-col gap-2">
          <p>{t("new.uploading", { sent: mb(s.sent), total: mb(s.total) })}</p>
          <div className="h-1.5 bg-line"><div className="h-1.5 bg-blue" style={{ width: `${s.total ? (100 * s.sent) / s.total : 0}%` }} /></div>
        </div>
      )}
      {s.step === "sections" && (
        <FileReview files={s.files} busy={false} status={null} onCancel={() => { setParams({}); dispatch({ type: "reset" }); }}
          onStart={async choices => {
            dispatch({ type: "start" });
            try { await startUploaded(s.id, choices); nav(`/app/checks/${s.id}`); }
            catch (e) { dispatch({ type: "fail", message: (e as Error).message }); }
          }} />
      )}
      {s.step === "running" && <p role="status">{t("new.running")}</p>}
      {s.step === "failed" && <Button onClick={() => dispatch({ type: "reset" })}>{t("new.restart")}</Button>}
    </section>
  );
}
