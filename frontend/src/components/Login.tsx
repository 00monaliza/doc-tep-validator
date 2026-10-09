import { useState } from "react";

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
    <section className="intake login" aria-labelledby="login-title">
      <h1 id="login-title">Сверка ТЭП между разделами проекта</h1>
      <p>
        {mode === "signin"
          ? "Войдите, чтобы загружать документы и видеть свои проверки. Доступ выдаёт администратор сервиса."
          : "Пришлём на почту ссылку, по которой можно задать новый пароль."}
      </p>
      <form onSubmit={submit}>
        <label>Почта
          <input type="email" autoComplete="username" required value={email}
            onChange={e => setEmail(e.target.value)} disabled={busy} />
        </label>
        {mode === "signin" && (
          <label>Пароль
            <input type="password" autoComplete="current-password" required value={password}
              onChange={e => setPassword(e.target.value)} disabled={busy} />
          </label>
        )}
        <div className="demo">
          <button type="submit" className="primary" disabled={busy || sent}>
            {mode === "signin" ? (busy ? "Входим…" : "Войти") : busy ? "Отправляем…" : "Прислать ссылку"}
          </button>
          <button type="button" className="link" disabled={busy}
            onClick={() => { setMode(m => (m === "signin" ? "reset" : "signin")); setError(""); setSent(false); }}>
            {mode === "signin" ? "Забыли пароль?" : "Назад ко входу"}
          </button>
        </div>
      </form>
      {sent && <div className="status" role="status">Письмо отправлено, проверьте почту (и папку «Спам»).</div>}
      <div className="status error" role="alert">{error}</div>
    </section>
  );
}
