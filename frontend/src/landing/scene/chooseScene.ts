export function chooseScene(env: { reducedMotion: boolean; width: number; webgl: boolean }): "scene" | "fallback" {
  return !env.reducedMotion && env.width >= 768 && env.webgl ? "scene" : "fallback";
}

export function hasWebGL(): boolean {
  try {
    const gl = document.createElement("canvas").getContext("webgl2");
    gl?.getExtension("WEBGL_lose_context")?.loseContext(); // only a probe: give the context back
    return !!gl;
  } catch { return false; }
}
