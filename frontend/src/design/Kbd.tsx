import type { ReactNode } from "react";

export default function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="font-mono text-[11px] border border-control border-b-2 rounded px-1 bg-sheet">{children}</kbd>;
}
