import { useContext } from "react";
import { Link } from "react-router";
import { useSession } from "../../app/providers";
import Button from "../../design/Button";
import { LangContext } from "../i18n";

export default function Hero() {
  const { tl } = useContext(LangContext);
  const { email } = useSession();
  return (
    <section id="hero" aria-labelledby="hero-title" className="px-4 md:px-6 pt-12 md:pt-24 pb-12 flex flex-col gap-6">
      <h1 id="hero-title" className="text-4xl md:text-6xl font-semibold leading-[1.05] tracking-tight">{tl("hero.title")}</h1>
      <p className="text-ink-2 md:text-xl max-w-xl">{tl("hero.lead")}</p>
      <div className="flex flex-wrap gap-3">
        <Link to="/demo"><Button variant="primary">{tl("hero.demo")}</Button></Link>
        {email
          ? <Link to="/app"><Button>{tl("nav.open")}</Button></Link>
          : <Link to="/login"><Button>{tl("hero.login")}</Button></Link>}
      </div>
    </section>
  );
}
