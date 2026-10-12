import { useContext } from "react";
import { LangContext } from "./i18n";

export default function Footer() {
  const { tl } = useContext(LangContext);
  return (
    <footer className="border-t border-line bg-sheet">
      <div className="max-w-6xl mx-auto px-4 md:px-6 py-8 flex flex-wrap gap-4 text-sm text-ink-2">
        <span className="flex-1 min-w-64">{tl("footer.thesis")}</span>
        <a href="https://github.com/00monaliza/doc-tep-validator" className="text-blue underline">{tl("footer.github")}</a>
      </div>
    </footer>
  );
}
