import type { Review } from "./types";

/** Saves of one finding run one after another; saves still waiting are replaced by the newest,
 * so quick repeated clicks end in the last choice and a failed save cannot overwrite a later one. */
export function createReviewQueue(save: (finding: number, r: Review) => Promise<void>) {
  const running = new Map<number, Promise<void>>();
  const waiting = new Map<number, { review: Review; resolvers: { ok: () => void; fail: (e: unknown) => void }[] }>();

  const run = (finding: number, review: Review): Promise<void> => {
    const p = save(finding, review).finally(() => {
      running.delete(finding);
      const next = waiting.get(finding);
      if (next) {
        waiting.delete(finding);
        run(finding, next.review).then(() => next.resolvers.forEach(x => x.ok()), e => next.resolvers.forEach(x => x.fail(e)));
      }
    });
    running.set(finding, p);
    return p;
  };

  return {
    push(finding: number, review: Review): Promise<void> {
      if (!running.has(finding)) return run(finding, review);
      return new Promise<void>((ok, fail) => {
        const w = waiting.get(finding);
        if (w) { w.review = review; w.resolvers.push({ ok, fail }); }
        else waiting.set(finding, { review, resolvers: [{ ok, fail }] });
      });
    },
  };
}
