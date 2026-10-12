import { Html, Line } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useContext, useMemo, useRef } from "react";
import { BoxGeometry, EdgesGeometry, type Group } from "three";
import { LangContext } from "../i18n";
import { LAYERS, layerY, numbersOpacity, ringProgress } from "./sceneMath";

const FLOOR = new EdgesGeometry(new BoxGeometry(4, 0.4, 3));
const NAMES: Record<(typeof LAYERS)[number], string> = { PZ: "ПЗ", AR: "АР", KR: "КР", SMETA: "См." };
const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#1E3A8A";

/** Ellipse around the mismatching value, drawn up to `share` of its length. */
function ring(share: number, y: number): [number, number, number][] {
  const n = Math.max(2, Math.round(64 * share));
  return Array.from({ length: n }, (_, k) => {
    const a = (k / 63) * Math.PI * 2;
    return [1.25 + Math.cos(a) * 0.95, y, 1.55 + Math.sin(a) * 0.35];
  });
}

function Building({ progress }: { progress: number }) {
  const group = useRef<Group>(null);
  const blue = useMemo(() => css("--blue"), []);
  const pencil = useMemo(() => css("--pencil"), []);
  // ПЗ on top: floor i of LAYERS sits at height of slot (3 − i)
  const y = (i: number) => layerY(progress, 3 - i) - layerY(progress, 3) / 2;
  const numbers = numbersOpacity(progress), drawn = ringProgress(progress);
  useFrame(state => {
    if (!group.current) return;
    group.current.rotation.y += (state.pointer.x * 0.14 - 0.5 - group.current.rotation.y) * 0.05;
    group.current.rotation.x += (-state.pointer.y * 0.08 - group.current.rotation.x) * 0.05;
  });
  return (
    <group ref={group}>
      {LAYERS.map((key, i) => (
        <group key={key} position={[0, y(i), 0]}>
          <lineSegments geometry={FLOOR}><lineBasicMaterial color={blue} /></lineSegments>
          <Html position={[-2.6, 0, 0]} center className="font-cond font-semibold text-sm text-ink-2 select-none">{NAMES[key]}</Html>
        </group>
      ))}
      {numbers > 0 && (
        <>
          <Html position={[1.25, y(0) + 0.05, 1.55]} center style={{ opacity: numbers }} className="num font-semibold text-blue select-none whitespace-nowrap">1 247,79</Html>
          <Html position={[1.25, y(1) + 0.05, 1.55]} center style={{ opacity: numbers }} className="num font-semibold text-pencil select-none whitespace-nowrap">1 382</Html>
        </>
      )}
      {drawn > 0 && (
        <>
          <Line points={ring(drawn, y(1))} color={pencil} lineWidth={2.2} />
          <Html position={[2.9, y(1) + 0.4, 1.55]} center style={{ opacity: drawn }} className="num font-semibold text-pencil select-none whitespace-nowrap">≠ 9,7 %</Html>
        </>
      )}
    </group>
  );
}

/** «Расслоение»: the building parts into ПЗ / АР / КР / смета as the page scrolls; the mismatch gets circled. */
export default function Scene({ progress }: { progress: number }) {
  const { tl } = useContext(LangContext);
  return (
    <div className="relative w-full h-full">
      <p className="sr-only">{tl("scene.alt")}</p>
      <Canvas aria-hidden="true" camera={{ position: [7, 5, 9], fov: 35 }} dpr={[1, 2]} gl={{ antialias: true, alpha: true }}>
        <Building progress={progress} />
      </Canvas>
    </div>
  );
}
