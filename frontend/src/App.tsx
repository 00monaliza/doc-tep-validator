import { useEffect, useState } from "react";
import { Unauthorized, getCapabilities, startDemo, startUploaded, uploadFiles, waitForCheck } from "./api";
import {
  authEnabled, authRedirect, currentEmail, initAuth, onSignedOut, requestPasswordReset, setPassword, signIn, signOut,
} from "./auth";
import FileReview from "./components/FileReview";
import Intake from "./components/Intake";
import Login from "./components/Login";
import ReportView from "./components/ReportView";
import SetPassword from "./components/SetPassword";
import type { Choice, Report, Reviews, UploadedFile } from "./types";

const ID_RE = /^[0-9a-f]{32}$/;

type Status = { text: string; error?: boolean } | null;
type Screen =
  | { kind: "loading" }
  | { kind: "login" }
  | { kind: "password"; invited: boolean }
  | { kind: "intake" }
  | { kind: "review"; id: string; files: Record<string, UploadedFile> }
  | { kind: "report"; id: string; report: Report; reviews: Reviews };

/** Who is signed in, for the header; null when the server needs no login (local run). */
export type Account = { email: string; onSignOut: () => void } | null;

export default function App() {
  const [screen, setScreen] = useState<Screen>({ kind: "loading" });
  const [status, setStatus] = useState<Status>(null);
  const [ocr, setOcr] = useState(true);
  const [email, setEmail] = useState<string | null>(null);

  const fail = (e: unknown) => {
    if (e instanceof Unauthorized) { setEmail(null); setScreen({ kind: "login" }); setStatus(null); return; }
    setStatus({ text: (e as Error).message, error: true });
  };

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
      fail(e);
    }
  }

  async function upload(files: FileList) {
    setStatus({ text: "Загружаем файлы…" });
    const mb = (b: number) => (b / 2 ** 20).toLocaleString("ru-RU", { maximumFractionDigits: 1 });
    try {
      const { id, files: uploaded } = await uploadFiles(files, (sent, total) => setStatus({
        text: sent < total ? `Загружаем файлы: ${mb(sent)} из ${mb(total)} МБ…` : "Определяем разделы…",
      }));
      history.replaceState(null, "", `?check=${id}`);
      setScreen({ kind: "review", id, files: uploaded });
      setStatus(null);
    } catch (e) {
      fail(e);
    }
  }

  const reset = () => { history.replaceState(null, "", location.pathname); setScreen({ kind: "intake" }); setStatus(null); };

  // after sign-in (or with no login at all): open the check from the link, or the intake
  const enter = () => {
    const opened = new URLSearchParams(location.search).get("check");
    if (opened && ID_RE.test(opened)) { setScreen({ kind: "intake" }); follow(opened); } else setScreen({ kind: "intake" });
  };

  useEffect(() => {
    let unsubscribe = () => {};
    (async () => {
      const caps = await getCapabilities();
      setOcr(caps.ocr);
      await initAuth(caps.auth);
      unsubscribe = onSignedOut(() => { setEmail(null); setScreen({ kind: "login" }); });
      const who = await currentEmail();
      setEmail(who);
      const link = authRedirect(); // an invitation or reset link signs the user in without a password yet
      if (who && link.kind) setScreen({ kind: "password", invited: link.kind === "invite" });
      else if (authEnabled() && !who) setScreen({ kind: "login" });
      else enter();
    })();
    return () => unsubscribe();
  }, []);

  const account: Account = email ? { email, onSignOut: () => { signOut(); } } : null;

  if (screen.kind === "loading") return <div className="intake"><p>Загрузка…</p></div>;
  if (screen.kind === "login") {
    return (
      <Login
        notice={authRedirect().error}
        onSignIn={async (e, p) => { await signIn(e, p); setEmail(await currentEmail()); enter(); }}
        onReset={requestPasswordReset}
      />
    );
  }
  if (screen.kind === "password") {
    return (
      <SetPassword email={email ?? ""} invited={screen.invited}
        onSet={async p => { await setPassword(p); history.replaceState(null, "", location.pathname); enter(); }} />
    );
  }
  if (screen.kind === "report") {
    return (
      <ReportView checkId={screen.id} report={screen.report} initialReviews={screen.reviews} onReset={reset}
        account={account} onUnauthorized={() => fail(new Unauthorized())} />
    );
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
      status={status} ocr={ocr} account={account}
      onFiles={upload}
      onDemo={(lang, kind) => follow(startDemo(lang, kind), kind === "scan")}
    />
  );
}
