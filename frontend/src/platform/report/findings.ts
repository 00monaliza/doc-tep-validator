import { SECTION, TYPE } from "../../lib/labels";
import type { Finding, Review } from "../../lib/types";

/** What a finding compares: a section pair, or the check type when both places are in one section. */
export function comparedLabel(f: Finding): string {
  const [a, b] = f.refs;
  return !b || a.section === b.section ? (TYPE[f.type] ?? f.type) : `${SECTION[a.section]} ↔ ${SECTION[b.section]}`;
}

export interface Filter {
  building: string; compared: string; flag: "" | "expert" | "noscan";
  review: "" | "none" | "confirmed" | "false_positive";
}
export const NO_FILTER: Filter = { building: "", compared: "", flag: "", review: "" };

export function applyFilter(list: Finding[], f: Filter, reviewOf: (x: Finding) => Review | undefined): Finding[] {
  return list.filter(x => {
    const v = reviewOf(x)?.verdict ?? null;
    return (!f.building || (x.object_name ?? "") === f.building)
      && (!f.compared || comparedLabel(x) === f.compared)
      && (f.flag !== "expert" || x.needs_expert)
      && (f.flag !== "noscan" || !x.low_confidence)
      && (!f.review || (f.review === "none" ? v === null : v === f.review));
  });
}
