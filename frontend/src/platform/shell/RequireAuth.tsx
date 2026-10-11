import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { useSession } from "../../app/providers";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const s = useSession();
  const loc = useLocation();
  if (!s.ready) return <p className="p-6 text-ink-2">Загрузка…</p>;
  if (s.enabled && !s.email) return <Navigate to={"/login?next=" + encodeURIComponent(loc.pathname + loc.search)} replace />;
  return <>{children}</>;
}
