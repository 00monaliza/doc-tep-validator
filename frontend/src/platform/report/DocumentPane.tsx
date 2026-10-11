import { useEffect, useState } from "react";
import Button from "../../design/Button";
import Kbd from "../../design/Kbd";
import type { Finding, Ref, Report } from "../../lib/types";
import RefPane from "./RefPane";
import { t } from "../../lib/i18n";

const SPLIT_KEY = "tep.split";
const readSplit = () => { try { return localStorage.getItem(SPLIT_KEY) !== "0"; } catch { return true; } };

const typing = (e: KeyboardEvent) =>
  e.target instanceof HTMLElement && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName);

interface Props { checkId: string; report: Report; selection: { refs: Ref[]; finding?: Finding } | null }

/** The centre of the report: the pages of the open finding, side by side or one at a time. */
export default function DocumentPane({ checkId, report, selection }: Props) {
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
    <section className="flex flex-col min-h-[70vh] lg:min-h-0 min-w-0" aria-label={t("doc.region")}>
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-line bg-sheet">
        {refs.length > 1 && (
          <Button size="sm" variant={split ? "primary" : "secondary"} aria-pressed={split} title={t("doc.keyS")}
            onClick={() => setSplit(v => !v)}>{split ? t("report.split") : t("report.single")}</Button>
        )}
        <span className="flex-1" />
        <details className="relative">
          <summary aria-label={t("doc.keys")} className="list-none cursor-pointer w-[26px] h-[26px] grid place-items-center border border-control rounded-full font-cond font-semibold text-ink-2">?</summary>
          <ul className="absolute right-0 top-8 z-20 w-max bg-sheet border border-ink shadow-lg px-3 py-2 text-sm flex flex-col gap-1">
            <li><Kbd>j</Kbd> / <Kbd>k</Kbd>{t("doc.keys.findings")}</li>
            <li><Kbd>←</Kbd> / <Kbd>→</Kbd>{t("doc.keys.places")}</li>
            <li><Kbd>s</Kbd>{t("doc.keys.split")}</li>
            <li><Kbd>1</Kbd> / <Kbd>2</Kbd>{t("doc.keys.verdict")}</li>
          </ul>
        </details>
      </div>
      <div className={sideBySide ? "flex-1 grid grid-cols-1 md:grid-cols-2 min-h-0 [&>*+*]:border-t md:[&>*+*]:border-t-0 md:[&>*+*]:border-l [&>*+*]:border-line" : "flex-1 grid min-h-0"}>
        {pane(left, setLeft)}
        {sideBySide && right >= 0 && pane(right, setRight)}
      </div>
    </section>
  );
}
