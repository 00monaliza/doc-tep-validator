import { NavLink } from "react-router";
import { t } from "../../lib/i18n";

const item = ({ isActive }: { isActive: boolean }) =>
  "block rounded px-2.5 py-1.5 text-sm " + (isActive ? "bg-[#2c3b3c] text-white" : "text-[#cfd8d4] hover:text-white");

export default function Sidebar() {
  return (
    <nav aria-label="Разделы" className="w-52 shrink-0 bg-[#1E2A2B] p-3 flex flex-col gap-0.5">
      <p className="font-cond font-semibold text-white px-2.5 pb-3">{t("app.name")}</p>
      <NavLink to="/app" end className={item}>{t("nav.checks")}</NavLink>
      <NavLink to="/app/new" className={item}>+ {t("nav.new")}</NavLink>
      <a href="/demo" className={item({ isActive: false })}>{t("nav.demo")}</a>
      <a href="/#research" className={item({ isActive: false })}>{t("nav.method")}</a>
      <span className="flex-1" />
      <NavLink to="/app/settings" className={item}>{t("nav.settings")}</NavLink>
    </nav>
  );
}
