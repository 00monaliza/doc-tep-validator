import { useEffect } from "react";
import type { ExpertVerdict, Finding } from "../../lib/types";

const typing = (t: EventTarget | null) => t instanceof HTMLElement && /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName);

/** j/k (о/л on the Russian layout) walk the visible findings, 1/2 set the verdict of the open one. */
export function useReportKeys(o: {
  list: Finding[]; current: Finding | null; pick: (f: Finding) => void;
  toggleVerdict: (f: Finding, v: ExpertVerdict) => void; enabled: boolean;
}) {
  useEffect(() => {
    if (!o.enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      if ((e.key === "1" || e.key === "2") && o.current) {
        e.preventDefault();
        o.toggleVerdict(o.current, e.key === "1" ? "confirmed" : "false_positive");
        return;
      }
      const step = e.key === "j" || e.key === "о" ? 1 : e.key === "k" || e.key === "л" ? -1 : 0;
      if (!step || !o.list.length) return;
      e.preventDefault();
      const i = o.current ? o.list.indexOf(o.current) : -1;
      o.pick(o.list[i < 0 ? 0 : Math.min(o.list.length - 1, Math.max(0, i + step))]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
}
