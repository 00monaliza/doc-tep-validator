import { useState } from "react";
import type { Account } from "../App";

interface Props {
  status: { text: string; error?: boolean } | null;
  ocr: boolean; // the server can read scans (no Tesseract on Vercel)
  account: Account;
  onFiles: (files: FileList) => void;
  onDemo: (lang: "ru" | "kz", kind: "text" | "scan") => void;
}

export default function Intake({ status, ocr, account, onFiles, onDemo }: Props) {
  const [over, setOver] = useState(false);
  const busy = status != null && !status.error;

  return (
    <section className="intake" aria-labelledby="intake-title">
      {account && (
        <div className="account">
          {account.email} · <button type="button" className="link" onClick={account.onSignOut}>выйти</button>
        </div>
      )}
      <h1 id="intake-title">Сверка ТЭП между разделами проекта</h1>
      <p>
        Загрузите пояснительную записку, текстовую часть АР и КР и сметную документацию на русском или
        казахском языке. Сервис найдёт технико-экономические показатели и покажет, где разделы расходятся.
      </p>
      <label
        className={`drop${over ? " over" : ""}`}
        onDragEnter={e => { e.preventDefault(); setOver(true); }}
        onDragOver={e => { e.preventDefault(); setOver(true); }}
        onDragLeave={e => { e.preventDefault(); setOver(false); }}
        onDrop={e => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files); }}
      >
        <strong>Выберите файлы или перетащите их сюда</strong>
        <span>PDF или DOCX, до 20 файлов по 50 МБ</span>
        <input
          type="file" multiple accept=".pdf,.docx" disabled={busy}
          onChange={e => { if (e.target.files?.length) onFiles(e.target.files); }}
        />
      </label>
      <div className="demo">
        <span>Нет своих документов?</span>
        <button type="button" disabled={busy} onClick={() => onDemo("ru", "text")}>Пример на русском</button>
        <button type="button" disabled={busy} onClick={() => onDemo("kz", "text")}>Қазақша мысал</button>
        {ocr && <button type="button" disabled={busy} onClick={() => onDemo("kz", "scan")}>Пример-скан</button>}
      </div>
      {!ocr && (
        <p className="note">На этом сервере сканы (PDF без текстового слоя) не распознаются: нет Tesseract.
          Загружайте PDF с текстом или DOCX; сканы проверяются при локальном запуске.</p>
      )}
      <div className={`status${status?.error ? " error" : ""}`} role="status" aria-live="polite">
        {status?.text}
      </div>
    </section>
  );
}
