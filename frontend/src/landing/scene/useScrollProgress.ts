import { useEffect, useState } from "react";
import { clamp01 } from "./sceneMath";

/** Share of the scroll between the top of #startId and the bottom of #endId (0…1). */
export function useScrollProgress(startId: string, endId: string): number {
  const [p, setP] = useState(0);
  useEffect(() => {
    let frame = 0;
    const measure = () => {
      frame = 0;
      const start = document.getElementById(startId), end = document.getElementById(endId);
      if (!start || !end) return;
      const top = start.getBoundingClientRect().top + scrollY;
      const bottom = end.getBoundingClientRect().bottom + scrollY - innerHeight;
      setP(bottom > top ? clamp01((scrollY - top) / (bottom - top)) : 0);
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(measure); };
    measure();
    addEventListener("scroll", onScroll, { passive: true });
    addEventListener("resize", onScroll);
    return () => { removeEventListener("scroll", onScroll); removeEventListener("resize", onScroll); cancelAnimationFrame(frame); };
  }, [startId, endId]);
  return p;
}
