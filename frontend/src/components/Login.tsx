import { useState } from "react";

interface Props { onSignIn: (email: string, password: string) => Promise<void> }

/** Sign-in for experts; accounts are created by the administrator, there is no sign-up. */
export default function Login({ onSignIn }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSignIn(email.trim(), password);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <section className="intake login" aria-labelledby="login-title">
      <h1 id="login-title">Сверка ТЭП между разделами проекта</h1>
      <p>Войдите, чтобы загружать документы и видеть свои проверки. Доступ выдаёт администратор сервиса.</p>
      <form onSubmit={submit}>
        <label>Почта
          <input type="email" autoComplete="username" required value={email}
            onChange={e => setEmail(e.target.value)} disabled={busy} />
        </label>
        <label>Пароль
          <input type="password" autoComplete="current-password" required value={password}
            onChange={e => setPassword(e.target.value)} disabled={busy} />
        </label>
        <div className="demo">
          <button type="submit" className="primary" disabled={busy}>{busy ? "Входим…" : "Войти"}</button>
        </div>
      </form>
      <div className="status error" role="alert">{error}</div>
    </section>
  );
}
