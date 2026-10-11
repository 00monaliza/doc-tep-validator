import { SECTION, SECTION_FULL } from "../lib/labels";
import type { Section } from "../lib/types";

export default function SectionChip({ section, present = true }: { section: Section; present?: boolean }) {
  return (
    <span data-present={String(present)} title={`${SECTION_FULL[section]}${present ? "" : ": нет в пакете"}`}
      className={present
        ? "inline-grid place-items-center min-w-8 h-[22px] px-1 border border-ink rounded-sm font-cond text-[11.5px] font-semibold"
        : "inline-grid place-items-center min-w-8 h-[22px] px-1 border border-line text-ink-2 rounded-sm font-cond text-[11.5px] line-through"}>
      {SECTION[section]}
    </span>
  );
}
