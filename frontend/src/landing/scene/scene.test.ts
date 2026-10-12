import { describe, expect, it } from "vitest";
import { chooseScene } from "./chooseScene";
import { clamp01, LAYERS, layerY, numbersOpacity, ringProgress } from "./sceneMath";

describe("scene layout (pure)", () => {
  it("floors start together, spread by the middle and stay ordered", () => {
    expect(LAYERS.map((_, i) => layerY(0, i))).toEqual([0, 0.6, 1.2, 1.8]);
    expect(LAYERS.map((_, i) => layerY(0.5, i))).toEqual([0, 1.6, 3.2, 4.8]);
    expect(layerY(1, 3)).toBe(layerY(0.5, 3));
    for (let p = 0; p <= 1; p += 0.05) expect(layerY(p + 0.05, 2)).toBeGreaterThanOrEqual(layerY(p, 2));
  });

  it("numbers appear after the floors part, the ring last", () => {
    expect(numbersOpacity(0.3)).toBe(0);
    expect(numbersOpacity(0.6)).toBe(1);
    expect(ringProgress(0.69)).toBe(0);
    expect(ringProgress(0.8)).toBeCloseTo(0.5);
    expect(ringProgress(1)).toBe(1);
    expect(clamp01(-1)).toBe(0);
  });

  it("the live scene only where it can run (Review Focus 4)", () => {
    expect(chooseScene({ reducedMotion: false, width: 1366, webgl: true })).toBe("scene");
    expect(chooseScene({ reducedMotion: true, width: 1366, webgl: true })).toBe("fallback");
    expect(chooseScene({ reducedMotion: false, width: 375, webgl: true })).toBe("fallback");
    expect(chooseScene({ reducedMotion: false, width: 1366, webgl: false })).toBe("fallback");
  });
});
