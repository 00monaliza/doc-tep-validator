import { type ReactNode, useEffect, useState } from "react";
import type { Finding, Ref, Report } from "../types";
import RefPane from "./RefPane";

const SPLIT_KEY = "tep.split";
const readSplit = () => { try { return localStorage.getItem(SPLIT_KEY) !== "0"; } catch { return true; } };

const typing = (e: KeyboardEvent) =>
  e.target instanceof HTMLElement && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName);

interface Props {
  checkId: string; report: Report; selection: { refs: Ref[]; finding?: Finding } | null;
  top?: ReactNode; // e.g. the expert's verdict on the open finding
}

export default function Viewer({ checkId, report, selection, top }: Props) {
  const refs = selection?.refs ?? [];
  const [split, setSplit] = useState(readSplit);
  const [left, setLeft] = useState(0);
  const [right, setRight] = useState(1);
  const sideBySide = split && refs.length > 1;

  // start on places that actually hold a value; the right pane gets the next one
  useEffect(() => {
    const valued = refs.map((r, i) => (r.value != null ? i : -1)).filter(i => i >= 0);
    const l = valued[0] ?? 0;
    setLeft(l);
    setRight(refs.findIndex((_, i) => i !== l));
  }, [selection]);

  useEffect(() => {
    try { localStorage.setItem(SPLIT_KEY, split ? "1" : "0"); } catch { /* storage may be blocked */ }
  }, [split]);

  // ←/→ walk the places: the only pane in single mode, the right (compared) pane side by side
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (typing(e) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "s" || e.key === "ы") { setSplit(v => !v); return; }
      if ((e.key !== "ArrowLeft" && e.key !== "ArrowRight") || refs.length < 2) return;
      e.preventDefault();
      const step = e.key === "ArrowRight" ? 1 : -1;
      const n = refs.length;
      if (!sideBySide) { setLeft(i => (i + step + n) % n); return; }
      setRight(i => {
        let j = (i + step + n) % n;
        if (j === left) j = (j + step + n) % n;
        return j;
      });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [refs, sideBySide, left]);

  const pane = (idx: number, onIdx: (i: number) => void) => (
    <RefPane
      checkId={checkId} report={report} refs={refs} idx={idx} onIdx={onIdx}
      finding={selection?.finding} showSwitch={!sideBySide || refs.length > 2}
    />
  );

  return (
    <section className="panel viewer" aria-label="Документ">
      {(top || refs.length > 1) && (
        <div className="viewer-bar">
          {top}
          {refs.length > 1 && (
            <button type="button" className="toggle" aria-pressed={split} onClick={() => setSplit(v => !v)}
              title="Клавиша s">
              {split ? "Рядом" : "По одному"}
            </button>
          )}
          <details className="keys">
            <summary aria-label="Клавиши">?</summary>
            <ul>
              <li><kbd>j</kbd> / <kbd>k</kbd> — следующее / предыдущее замечание</li>
              <li><kbd>←</kbd> / <kbd>→</kbd> — места замечания</li>
              <li><kbd>s</kbd> — рядом / по одному</li>
              <li><kbd>1</kbd> / <kbd>2</kbd> — подтверждаю / ложное</li>
            </ul>
          </details>
        </div>
      )}
      <div className={sideBySide ? "panes split" : "panes"}>
        {pane(left, setLeft)}
        {sideBySide && right >= 0 && pane(right, setRight)}
      </div>
    </section>
  );
}
