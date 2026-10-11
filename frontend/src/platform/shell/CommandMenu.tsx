import { useQueryClient } from "@tanstack/react-query";
import { Command as Cmdk } from "cmdk";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { useSession } from "../../app/providers";
import Dialog from "../../design/Dialog";
import Kbd from "../../design/Kbd";
import { useTheme } from "../../design/theme";
import { exportXlsx } from "../../lib/export";
import { t } from "../../lib/i18n";
import { useChecks } from "../../lib/queries";
import type { CheckStatus } from "../../lib/types";
import { buildCommands, type Command } from "./commands";

export default function CommandMenu() {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const loc = useLocation();
  const qc = useQueryClient();
  const session = useSession();
  const { resolved, setTheme } = useTheme();
  const checks = useChecks();
  const checkId = loc.pathname.match(/^\/app\/checks\/([0-9a-f]{32})/)?.[1] ?? null;
  const data = checkId ? qc.getQueryData<CheckStatus>(["check", checkId]) : undefined;
  const report = data?.status === "done" ? data : null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(o => !o); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const cmds = buildCommands({ checks: checks.data ?? [], report: report?.report ?? null, checkId, theme: resolved, canSignOut: session.enabled });
  const run = (c: Command) => {
    setOpen(false);
    switch (c.run.type) {
      case "go": nav(c.run.to); break;
      case "finding": nav(`/app/checks/${checkId}?f=${c.run.index}`); break;
      case "export": if (report && checkId) exportXlsx(report.report, report.reviews ?? {}, checkId); break;
      case "theme": setTheme(resolved === "dark" ? "light" : "dark"); break;
      case "signout": session.signOut(); break;
    }
  };
  const groups = ["Действия", "Проверки", "Замечания"] as const;

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}
        className="flex items-center gap-2 min-h-8 px-2.5 border border-control rounded bg-sheet text-ink-2 text-sm w-72">
        {t("search.hint")} <span className="flex-1" /><Kbd>⌘K</Kbd>
      </button>
      <Dialog open={open} onOpenChange={setOpen} title={t("search.hint")}>
        <Cmdk label={t("search.hint")} className="flex flex-col">
          <Cmdk.Input placeholder={t("search.placeholder")} className="m-3 min-h-9 border border-control rounded px-2.5 bg-sheet" />
          <Cmdk.List className="max-h-80 overflow-auto px-2 pb-2">
            <Cmdk.Empty className="p-3 text-ink-2">Ничего не найдено</Cmdk.Empty>
            {groups.map(g => {
              const items = cmds.filter(c => c.group === g);
              return items.length ? (
                <Cmdk.Group key={g} heading={g} className="[&_[cmdk-group-heading]]:font-cond [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:text-ink-2 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pt-2">
                  {items.map(c => (
                    <Cmdk.Item key={c.id} value={`${c.label} ${c.id}`} onSelect={() => run(c)}
                      className="px-2 py-1.5 rounded cursor-pointer data-[selected=true]:bg-blue-wash">{c.label}</Cmdk.Item>
                  ))}
                </Cmdk.Group>
              ) : null;
            })}
          </Cmdk.List>
        </Cmdk>
      </Dialog>
    </>
  );
}
