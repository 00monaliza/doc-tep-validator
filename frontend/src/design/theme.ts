import { useCallback, useEffect, useState } from "react";

export type ThemeChoice = "system" | "light" | "dark";
const KEY = "tep.theme";

const read = (): ThemeChoice => {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch { return "system"; }
};
const systemDark = () => typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;

/** «Калька» / «Синька»: the explicit choice wins, otherwise the system setting. */
export function useTheme() {
  const [theme, setThemeState] = useState<ThemeChoice>(read);
  const resolved: "light" | "dark" = theme === "system" ? (systemDark() ? "dark" : "light") : theme;

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme"); else root.dataset.theme = theme;
  }, [theme]);

  const setTheme = useCallback((t: ThemeChoice) => {
    try { if (t === "system") localStorage.removeItem(KEY); else localStorage.setItem(KEY, t); } catch { /* blocked storage */ }
    setThemeState(t);
  }, []);

  return { theme, resolved, setTheme };
}
