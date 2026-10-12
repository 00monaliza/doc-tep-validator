import { t } from "../../lib/i18n";
import { fieldName } from "../../lib/labels";
import type { CheckRow, Report } from "../../lib/types";

export type CommandRun =
  | { type: "go"; to: string } | { type: "export" } | { type: "theme" } | { type: "signout" } | { type: "finding"; index: number };
export interface Command { id: string; group: "Действия" | "Проверки" | "Замечания"; label: string; run: CommandRun }

export function buildCommands(i: { checks: CheckRow[]; report: Report | null; checkId: string | null; theme: "light" | "dark"; canSignOut: boolean }): Command[] {
  const out: Command[] = [{ id: "new", group: "Действия", label: t("cmd.new"), run: { type: "go", to: "/app/new" } }];
  if (i.report) out.push({ id: "export", group: "Действия", label: t("cmd.export"), run: { type: "export" } });
  out.push({ id: "theme", group: "Действия", label: t("cmd.theme"), run: { type: "theme" } });
  if (i.canSignOut) out.push({ id: "signout", group: "Действия", label: t("cmd.signout"), run: { type: "signout" } });
  for (const c of i.checks) out.push({ id: `check-${c.id}`, group: "Проверки", label: c.title, run: { type: "go", to: `/app/checks/${c.id}` } });
  i.report?.findings.forEach((f, index) => {
    if (f.verdict !== "MATCH") out.push({ id: `finding-${index}`, group: "Замечания", label: fieldName(f.field), run: { type: "finding", index } });
  });
  return out;
}
