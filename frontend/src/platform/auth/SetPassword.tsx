import { useState } from "react";

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
    if (password.length < MIN) { setError(`Пароль — не короче ${MIN} символов.`); return; }
    if (password !== repeat) { setError("Пароли не совпадают."); return; }
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
    <section className="intake login" aria-labelledby="password-title">
      <h1 id="password-title">{invited ? "Добро пожаловать" : "Новый пароль"}</h1>
      <p>{invited ? `Аккаунт ${email} создан. Задайте пароль, с ним вы будете входить в сервис.`
        : `Задайте новый пароль для ${email}.`}</p>
      <form onSubmit={submit}>
        <label>Пароль
          <input type="password" autoComplete="new-password" required minLength={MIN} value={password}
            onChange={e => setPassword(e.target.value)} disabled={busy} />
        </label>
        <label>Ещё раз
          <input type="password" autoComplete="new-password" required value={repeat}
            onChange={e => setRepeat(e.target.value)} disabled={busy} />
        </label>
        <div className="demo">
          <button type="submit" className="primary" disabled={busy}>{busy ? "Сохраняем…" : "Сохранить и войти"}</button>
        </div>
      </form>
      <div className="status error" role="alert">{error}</div>
    </section>
  );
}
