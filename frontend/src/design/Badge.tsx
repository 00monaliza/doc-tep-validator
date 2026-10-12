import clsx from "clsx";
import type { ReactNode } from "react";

export type BadgeKind = "mismatch" | "missing" | "match" | "expert" | "scan" | "confirmed" | "false_positive";
const KIND: Record<BadgeKind, string> = {
  mismatch: "text-pencil bg-pencil-wash border-pencil",
  missing: "text-amber bg-amber-wash border-amber",
  match: "text-green bg-green-wash border-green",
  expert: "text-blue bg-blue-wash border-blue",
  scan: "text-amber bg-amber-wash border-amber",
  confirmed: "text-green bg-green-wash border-green",
  false_positive: "text-ink-2 border-ink-2 line-through",
};

export default function Badge({ kind, children }: { kind: BadgeKind; children: ReactNode }) {
  return (
    <span data-kind={kind} className={clsx(
      "inline-block border rounded-sm px-1.5 py-px font-cond text-[11px] font-semibold uppercase tracking-wide", KIND[kind])}>
      {children}
    </span>
  );
}
