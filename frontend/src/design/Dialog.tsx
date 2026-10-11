import * as D from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

export default function Dialog({ open, onOpenChange, title, children }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; children: ReactNode;
}) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 bg-black/30 z-40" />
        <D.Content className="fixed left-1/2 top-[15vh] -translate-x-1/2 z-50 w-[min(560px,calc(100vw-32px))] bg-sheet border border-ink rounded shadow-lg">
          <D.Title className="font-cond text-sm font-semibold uppercase tracking-wide text-ink-2 px-4 pt-3">{title}</D.Title>
          {children}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}
