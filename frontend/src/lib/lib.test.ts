import { describe, expect, it, vi } from "vitest";
import { t } from "./i18n";
import { createReviewQueue } from "./reviewQueue";
import type { Review } from "./types";

const r = (verdict: Review["verdict"], comment = ""): Review => ({ verdict, comment });

describe("review queue", () => {
  it("saves one finding strictly in order and collapses waiting saves into the last", async () => {
    const calls: string[] = [];
    let release!: () => void;
    const save = vi.fn((finding: number, rv: Review) => {
      calls.push(`${finding}:${rv.verdict}`);
      return calls.length === 1 ? new Promise<void>(res => { release = res; }) : Promise.resolve();
    });
    const q = createReviewQueue(save);
    const a = q.push(0, r("confirmed"));
    const b = q.push(0, r("false_positive"));
    const c = q.push(0, r(null));
    release();
    await Promise.all([a, b, c]);
    expect(calls).toEqual(["0:confirmed", "0:null"]);
  });

  it("different findings do not wait for each other", async () => {
    const save = vi.fn(() => new Promise<void>(() => {})); // never resolves
    const q = createReviewQueue(save);
    q.push(0, r("confirmed"));
    q.push(1, r("confirmed"));
    expect(save).toHaveBeenCalledTimes(2);
  });

  it("a failed save rejects its promise and the next one still runs", async () => {
    const save = vi.fn().mockRejectedValueOnce(new Error("500")).mockResolvedValue(undefined);
    const q = createReviewQueue(save);
    await expect(q.push(0, r("confirmed"))).rejects.toThrow("500");
    await expect(q.push(0, r("false_positive"))).resolves.toBeUndefined();
  });
});

describe("i18n", () => {
  it("substitutes variables", () => {
    expect(t("checks.count", { n: 4 })).toBe("Мои проверки · 4");
  });
});
