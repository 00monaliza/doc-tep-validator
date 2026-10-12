import clsx from "clsx";

export interface StampItem { label: string; value: string; tone?: "bad" | "warn" | "ok" }
const TONE = { bad: "text-pencil", warn: "text-amber", ok: "text-green" };

/** The title-block of a drawing: key numbers of a check in one framed row. */
export default function StampSummary({ items }: { items: StampItem[] }) {
  return (
    // cells draw their right and bottom rules; the frame's overflow clips the outer ones, so a wrapped row leaves no gap
    <dl className="grid overflow-hidden border-2 border-ink bg-sheet" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(104px, 1fr))" }}>
      {items.map(it => (
        <div key={it.label} data-tone={it.tone ?? "none"} className="px-3 py-1.5 min-w-0 shadow-[1px_0_0_var(--ink),0_1px_0_var(--ink)]">
          <dt className="font-cond text-[11px] text-ink-2 truncate">{it.label}</dt>
          <dd className={clsx("num text-xl font-semibold", it.tone && TONE[it.tone])}>{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}
