import { Link } from "react-router";
import Button from "../design/Button";
import { t } from "../lib/i18n";
import DemoReport from "./DemoReport";

export default function DemoPage() {
  return (
    <div className="flex flex-col h-full">
      <header className="flex flex-wrap items-center gap-3 px-4 py-2 bg-sheet border-b border-line">
        <Link to="/" className="font-cond font-semibold">{t("app.name")}</Link>
        <span className="text-sm text-ink-2 flex-1 min-w-48">{t("demo.banner")}</span>
        <Link to="/#access"><Button size="sm">{t("demo.request")}</Button></Link>
        <Link to="/login"><Button size="sm" variant="primary">{t("demo.login")}</Button></Link>
      </header>
      <div className="flex-1 min-h-0 overflow-auto"><DemoReport /></div>
    </div>
  );
}
