import { lazy, Suspense } from "react";
import { Navigate, type RouteObject } from "react-router";
import AppShell from "../platform/shell/AppShell";
import RequireAuth from "../platform/shell/RequireAuth";
import LoginPage from "../platform/auth/LoginPage";
import SettingsPage from "../platform/settings/SettingsPage";
import { t } from "../lib/i18n";

const ChecksPage = lazy(() => import("../platform/checks/ChecksPage"));
const NewCheckPage = lazy(() => import("../platform/new/NewCheckPage"));
const ReportPage = lazy(() => import("../platform/report/ReportPage"));
const page = (el: JSX.Element) => <Suspense fallback={<p className="p-6 text-ink-2">{t("common.loading")}</p>}>{el}</Suspense>;

const ID_RE = /^[0-9a-f]{32}$/;
/** `/?check=<id>` links from the old interface. */
export function legacyRedirect(search: string): string | null {
  const id = new URLSearchParams(search).get("check");
  return id && ID_RE.test(id) ? `/app/checks/${id}` : null;
}

function Root() {
  return <Navigate to={legacyRedirect(location.search) ?? "/app"} replace />;
}

export const routes: RouteObject[] = [
  { path: "/", element: <Root /> },
  { path: "/login", element: <LoginPage /> },
  {
    path: "/app",
    element: <RequireAuth><AppShell /></RequireAuth>,
    children: [
      { index: true, element: page(<ChecksPage />) },
      { path: "new", element: page(<NewCheckPage />) },
      { path: "checks/:id", element: page(<ReportPage />) },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/app" replace /> },
];
