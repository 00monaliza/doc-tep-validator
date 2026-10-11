import { useSession } from "../../app/providers";
import Button from "../../design/Button";
import { useTheme, type ThemeChoice } from "../../design/theme";
import { useToast } from "../../design/Toast";
import { requestPasswordReset } from "../../lib/auth";
import { t } from "../../lib/i18n";

export default function SettingsPage() {
  const s = useSession();
  const toast = useToast();
  const { theme, setTheme } = useTheme();
  const opts: [ThemeChoice, string][] = [["system", t("settings.theme.system")], ["light", t("settings.theme.light")], ["dark", t("settings.theme.dark")]];
  return (
    <section className="max-w-xl p-6 flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">{t("nav.settings")}</h1>
      <fieldset className="flex flex-col gap-2">
        <legend className="font-cond text-xs uppercase tracking-wide text-ink-2 mb-1">{t("settings.theme")}</legend>
        {opts.map(([v, label]) => (
          <label key={v} className="flex items-center gap-2 min-h-[26px]">
            <input type="radio" name="theme" checked={theme === v} onChange={() => setTheme(v)} /> {label}
          </label>
        ))}
      </fieldset>
      {s.enabled && (
        <div className="flex flex-col gap-2">
          <p className="font-cond text-xs uppercase tracking-wide text-ink-2">{t("settings.account")}</p>
          <p>{s.email}</p>
          <div className="flex gap-2">
            <Button onClick={() => s.email && requestPasswordReset(s.email)
              .then(() => toast(t("settings.password.sent")), e => toast((e as Error).message, "error"))}>{t("settings.password")}</Button>
            <Button variant="ghost" onClick={() => s.signOut()}>{t("settings.signout")}</Button>
          </div>
        </div>
      )}
    </section>
  );
}
