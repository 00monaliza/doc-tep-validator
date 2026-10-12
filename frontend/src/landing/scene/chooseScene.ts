export function chooseScene(env: { reducedMotion: boolean; width: number; webgl: boolean }): "scene" | "fallback" {
  return !env.reducedMotion && env.width >= 768 && env.webgl ? "scene" : "fallback";
}

export function hasWebGL(): boolean {
  try { return !!document.createElement("canvas").getContext("webgl2"); } catch { return false; }
}
