import { useState } from "react";
import Button from "../../design/Button";
import { t } from "../../lib/i18n";

const MIN = 8;

interface Props {
  email: string;
  invited: boolean; // an invitation (first password) rather than a reset
  onSet: (password: string) => Promise<void>;
}

/** After an invitation or a reset link: the user is signed in and chooses a password. */
export default function SetPassword({ email, invited, onSet }: Props) {
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < MIN) { setError(t("password.tooShort", { n: MIN })); return; }
    if (password !== repeat) { setError(t("password.mismatch")); return; }
    setBusy(true);
    setError("");
    try {
      await onSet(password);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <section className="max-w-md mx-auto my-[10vh] px-4 flex flex-col gap-4" aria-labelledby="password-title">
      <h1 id="password-title" className="text-2xl font-semibold">{invited ? t("password.welcome") : t("password.new")}</h1>
      <p className="text-ink-2">{invited ? t("password.invited.lead", { email })
        : t("password.reset.lead", { email })}</p>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm text-ink-2">{t("login.password")}
          <input className="min-h-9 border border-control rounded px-2.5 bg-sheet text-ink text-base" type="password" autoComplete="new-password" required minLength={MIN} value={password}
            onChange={e => setPassword(e.target.value)} disabled={busy} />
        </label>
        <label className="flex flex-col gap-1 text-sm text-ink-2">{t("password.repeat")}
          <input className="min-h-9 border border-control rounded px-2.5 bg-sheet text-ink text-base" type="password" autoComplete="new-password" required value={repeat}
            onChange={e => setRepeat(e.target.value)} disabled={busy} />
        </label>
        <div className="flex items-center gap-3">
          <Button type="submit" variant="primary" disabled={busy}>{busy ? t("password.saving") : t("password.save")}</Button>
        </div>
      </form>
      <div className="text-pencil text-sm" role="alert">{error}</div>
    </section>
  );
}
