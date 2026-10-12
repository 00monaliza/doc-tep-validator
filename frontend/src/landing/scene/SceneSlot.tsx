import { lazy, Suspense, useState } from "react";
import { chooseScene, hasWebGL } from "./chooseScene";
import Fallback from "./Fallback";
import { useScrollProgress } from "./useScrollProgress";

const Scene = lazy(() => import("./Scene")); // own chunk: three.js loads only on the landing, after the text

/** The live scene where it can run, the SVG frames everywhere else (phones, reduced motion, no WebGL). */
export default function SceneSlot() {
  const progress = useScrollProgress("hero", "how");
  const [mode] = useState(() => chooseScene({
    reducedMotion: typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches,
    width: typeof innerWidth === "number" ? innerWidth : 0,
    webgl: hasWebGL(),
  }));
  if (mode === "fallback") return <Fallback progress={progress} />;
  return <Suspense fallback={<Fallback progress={0} />}><Scene progress={progress} /></Suspense>;
}
