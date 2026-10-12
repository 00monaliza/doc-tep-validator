export const LAYERS = ["PZ", "AR", "KR", "SMETA"] as const;
export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const ramp = (p: number, from: number, to: number) => clamp01((p - from) / (to - from));

/** Height of floor i: together at first, spread out by the middle of the scroll. */
export const layerY = (p: number, i: number) => +(i * (0.6 + 1.0 * ramp(p, 0.15, 0.5))).toFixed(4);
export const numbersOpacity = (p: number) => ramp(p, 0.35, 0.6);
export const ringProgress = (p: number) => ramp(p, 0.7, 0.9);
