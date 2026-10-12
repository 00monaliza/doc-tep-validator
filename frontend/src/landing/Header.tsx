import { useContext } from "react";
import { Link } from "react-router";
import { useSession } from "../app/providers";
import Button from "../design/Button";
import { t } from "../lib/i18n";
import { LangContext, type Lang } from "./i18n";

export default function Header() {
  const { lang, setLang, tl } = useContext(LangContext);
  const { email } = useSession();
  return (
    <header className="sticky top-0 z-20 bg-sheet/90 backdrop-blur border-b border-line">
      <div className="max-w-6xl mx-auto px-4 md:px-6 h-14 flex items-center gap-4">
        <Link to="/" className="font-cond font-semibold text-lg">{t("app.name")}</Link>
        <nav className="hidden md:flex gap-4 text-sm text-ink-2">
          <a href="#how" className="hover:text-ink">{tl("nav.how")}</a>
          <a href="#research" className="hover:text-ink">{tl("nav.research")}</a>
        </nav>
        <span className="flex-1" />
        <span className="flex" role="group" aria-label="RU / KZ">
          {(["ru", "kz"] as Lang[]).map(l => (
            <Button key={l} size="sm" variant={lang === l ? "primary" : "secondary"} aria-pressed={lang === l}
              onClick={() => setLang(l)} className="first:rounded-r-none last:rounded-l-none">{l.toUpperCase()}</Button>
          ))}
        </span>
        {email
          ? <Link to="/app"><Button size="sm" variant="primary">{tl("nav.open")}</Button></Link>
          : <Link to="/login"><Button size="sm">{tl("nav.login")}</Button></Link>}
      </div>
    </header>
  );
}
