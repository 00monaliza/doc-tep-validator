import { useEffect, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import { useSession } from "../../app/providers";
import { authRedirect, currentEmail, requestPasswordReset, setPassword, signIn } from "../../lib/auth";
import Login from "./Login";
import SetPassword from "./SetPassword";
import { t } from "../../lib/i18n";

/** Sign-in, and the "set a password" step after an invitation or reset link. */
export default function LoginPage() {
  const s = useSession();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next")?.startsWith("/app") ? params.get("next")! : "/app";
  const [email, setEmail] = useState<string | null>(null);
  useEffect(() => { currentEmail().then(setEmail); }, [s.email]);

  if (!s.ready) return <p className="p-6 text-ink-2">{t("common.loading")}</p>;
  if (!s.enabled) return <Navigate to={next} replace />;
  const link = authRedirect();
  if (email && link.kind) {
    return <SetPassword email={email} invited={link.kind === "invite"}
      onSet={async p => { await setPassword(p); await s.refresh(); nav(next, { replace: true }); }} />;
  }
  if (s.email) return <Navigate to={next} replace />;
  return <Login notice={link.error}
    onSignIn={async (e, p) => { await signIn(e, p); await s.refresh(); nav(next, { replace: true }); }}
    onReset={requestPasswordReset} />;
}
