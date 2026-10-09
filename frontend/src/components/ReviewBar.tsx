import { useEffect, useState } from "react";
import type { ExpertVerdict, Review } from "../types";

export const EXPERT: Record<ExpertVerdict, string> = { confirmed: "Подтверждаю", false_positive: "Ложное" };

interface Props {
  review: Review;
  onChange: (r: Review) => void;
  saving: boolean;
  error: string;
}

/** The expert's verdict on the open finding: confirm it or mark it as a false alarm, with a comment. */
export default function ReviewBar({ review, onChange, saving, error }: Props) {
  const [comment, setComment] = useState(review.comment);
  useEffect(() => setComment(review.comment), [review.comment]);

  const toggle = (v: ExpertVerdict) => onChange({ verdict: review.verdict === v ? null : v, comment });
  const saveComment = () => { if (comment.trim() !== review.comment) onChange({ ...review, comment: comment.trim() }); };

  return (
    <div className="review-bar">
      <span className="label">Вердикт эксперта</span>
      {(Object.keys(EXPERT) as ExpertVerdict[]).map((v, i) => (
        <button key={v} type="button" className={`expert x-${v}`} aria-pressed={review.verdict === v}
          onClick={() => toggle(v)} title={`Клавиша ${i + 1}`}>
          {EXPERT[v]} <kbd>{i + 1}</kbd>
        </button>
      ))}
      <input
        type="text" maxLength={2000} placeholder="Комментарий (Enter — сохранить)" value={comment}
        aria-label="Комментарий эксперта"
        onChange={e => setComment(e.target.value)}
        onBlur={saveComment}
        onKeyDown={e => { if (e.key === "Enter") { saveComment(); (e.target as HTMLInputElement).blur(); } }}
      />
      <span className={`save-state${error ? " error" : ""}`} role="status" aria-live="polite">
        {error || (saving ? "сохраняем…" : "")}
      </span>
    </div>
  );
}
