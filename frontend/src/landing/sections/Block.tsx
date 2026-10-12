import type { ReactNode } from "react";
import Reveal from "../Reveal";

/** One landing block: anchored section, title, content; every other block on tracing paper. */
export default function Block({ id, title, lead, tracing, children }: {
  id: string; title: string; lead?: string; tracing?: boolean; children?: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className={tracing ? "bg-tracing" : "bg-paper"}>
      <Reveal className="max-w-6xl mx-auto px-4 md:px-6 py-16 md:py-24 flex flex-col gap-6">
        <h2 id={`${id}-title`} className="text-2xl md:text-4xl font-semibold leading-tight max-w-3xl">{title}</h2>
        {lead && <p className="text-ink-2 max-w-2xl md:text-lg">{lead}</p>}
        {children}
      </Reveal>
    </section>
  );
}
