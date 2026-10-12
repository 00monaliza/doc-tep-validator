import { NavLink } from "react-router";
import { t } from "../../lib/i18n";

const item = ({ isActive }: { isActive: boolean }) =>
  "block rounded px-2.5 py-1.5 text-sm " + (isActive ? "bg-[#2c3b3c] text-white" : "text-[#cfd8d4] hover:text-white");

export default function Sidebar() {
  return (
    <nav aria-label={t("shell.sections")} className="hidden md:flex w-52 shrink-0 bg-[#1E2A2B] p-3 flex-col gap-0.5">
      <p className="font-cond font-semibold text-white px-2.5 pb-3">{t("app.name")}</p>
      <NavLink to="/app" end className={item}>{t("nav.checks")}</NavLink>
      <NavLink to="/app/new" className={item}>+ {t("nav.new")}</NavLink>
      <span className="flex-1" />
      <NavLink to="/app/settings" className={item}>{t("nav.settings")}</NavLink>
    </nav>
  );
}

/** The same links on a phone, behind «Меню» in the header. */
export function MobileMenu() {
  return (
    <details className="md:hidden relative">
      <summary role="button" aria-label={t("shell.menu")}
        className="list-none cursor-pointer min-h-8 px-2.5 grid place-items-center border border-control rounded bg-sheet text-sm">
        ☰
      </summary>
      <nav className="absolute left-0 top-10 z-30 w-56 bg-[#1E2A2B] p-2 flex flex-col gap-0.5 shadow-lg rounded">
        <NavLink to="/app" end className={item}>{t("nav.checks")}</NavLink>
        <NavLink to="/app/new" className={item}>+ {t("nav.new")}</NavLink>
        <NavLink to="/app/settings" className={item}>{t("nav.settings")}</NavLink>
      </nav>
    </details>
  );
}
