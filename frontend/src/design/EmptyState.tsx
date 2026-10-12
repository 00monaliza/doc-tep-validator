import type { ReactNode } from "react";

export default function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2 p-6 text-ink-2">
      <p className="text-ink font-semibold">{title}</p>
      {children && <div className="text-sm">{children}</div>}
      {action}
    </div>
  );
}
