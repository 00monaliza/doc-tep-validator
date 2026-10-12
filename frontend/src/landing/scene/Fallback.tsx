import { useContext } from "react";
import { LangContext } from "../i18n";

const BLUE = "var(--blue)", PENCIL = "var(--pencil)", INK = "var(--ink-2)";
const FLOORS = ["ПЗ", "АР", "КР", "См."];

/** The «Расслоение» drawing without WebGL: whole building → floors apart → the mismatch circled. */
export default function Fallback({ progress = 1 }: { progress?: number }) {
  const { tl } = useContext(LangContext);
  const frame = progress < 0.25 ? 0 : progress < 0.7 ? 1 : 2;
  const gap = frame === 0 ? 18 : 42;
  const floor = (i: number) => {
    const y = 40 + i * gap;
    return (
      <g key={i}>
        <path d={`M160 ${y} L270 ${y + 40} L160 ${y + 80} L50 ${y + 40} Z`} fill="none" stroke={BLUE} strokeWidth={1.4} />
        {frame > 0 && <text x={14} y={y + 46} fontFamily="IBM Plex Sans Condensed" fontWeight={600} fontSize={13} fill={INK}>{FLOORS[i]}</text>}
      </g>
    );
  };
  return (
    <svg data-scene="fallback" viewBox="0 0 320 300" role="img" aria-label={tl("scene.alt")} className="w-full h-full">
      {[3, 2, 1, 0].map(floor)}
      {frame === 2 && (
        <g fontFamily="IBM Plex Mono" fontWeight={600} fontSize={12}>
          <text x={128} y={84} fill={BLUE}>1 247,79</text>
          <text x={138} y={84 + gap} fill={PENCIL}>1 382</text>
          <ellipse cx={160} cy={80 + gap} rx={44} ry={13} fill="none" stroke={PENCIL} strokeWidth={2.2} transform={`rotate(-3 160 ${80 + gap})`} />
          <text x={214} y={72 + gap} fill={PENCIL}>≠ 9,7 %</text>
        </g>
      )}
    </svg>
  );
}
