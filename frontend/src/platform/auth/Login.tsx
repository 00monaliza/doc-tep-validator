import { useState } from "react";
import Button from "../../design/Button";
import { t } from "../../lib/i18n";

interface Props {
  notice: string | null; // e.g. an expired invitation link
  onSignIn: (email: string, password: string) => Promise<void>;
  onReset: (email: string) => Promise<void>;
}

/** Sign-in for experts; accounts are created by the administrator, there is no sign-up. */
export default function Login({ notice, onSignIn, onReset }: Props) {
  const [mode, setMode] = useState<"signin" | "reset">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(notice ?? "");
  const [sent, setSent] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "signin") await onSignIn(email.trim(), password);
      else { await onReset(email.trim()); setSent(true); }
    } catch (err) {
      setError((err as Error).message);
    }
    setBusy(false);
  };

  return (
    <section className="max-w-md mx-auto my-[10vh] px-4 flex flex-col gap-4" aria-labelledby="login-title">
      <h1 id="login-title" className="text-2xl font-semibold">{t("login.title")}</h1>
      <p className="text-ink-2">
        {mode === "signin"
          ? t("login.lead")
          : t("login.reset.lead")}
      </p>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm text-ink-2">{t("login.email")}
          <input className="min-h-9 border border-control rounded px-2.5 bg-sheet text-ink text-base" type="email" autoComplete="username" required value={email}
            onChange={e => setEmail(e.target.value)} disabled={busy} />
        </label>
        {mode === "signin" && (
          <label className="flex flex-col gap-1 text-sm text-ink-2">{t("login.password")}
            <input className="min-h-9 border border-control rounded px-2.5 bg-sheet text-ink text-base" type="password" autoComplete="current-password" required value={password}
              onChange={e => setPassword(e.target.value)} disabled={busy} />
          </label>
        )}
        <div className="flex items-center gap-3">
          <Button type="submit" variant="primary" disabled={busy || sent}>
            {mode === "signin" ? (busy ? t("login.submitting") : t("login.submit")) : busy ? t("login.reset.submitting") : t("login.reset.submit")}
          </Button>
          <Button variant="ghost" disabled={busy}
            onClick={() => { setMode(m => (m === "signin" ? "reset" : "signin")); setError(""); setSent(false); }}>
            {mode === "signin" ? t("login.forgot") : t("login.back")}
          </Button>
        </div>
      </form>
      {sent && <div className="text-sm" role="status">{t("login.reset.sent")}</div>}
      <div className="text-pencil text-sm" role="alert">{error}</div>
    </section>
  );
}
