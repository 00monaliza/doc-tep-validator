import { lazy, Suspense } from "react";
import { isRouteErrorResponse, Navigate, useLocation, useRouteError, type RouteObject } from "react-router";
import Button from "../design/Button";
import AppShell from "../platform/shell/AppShell";
import RequireAuth from "../platform/shell/RequireAuth";
import LoginPage from "../platform/auth/LoginPage";
import SettingsPage from "../platform/settings/SettingsPage";
import { t } from "../lib/i18n";

const ChecksPage = lazy(() => import("../platform/checks/ChecksPage"));
const NewCheckPage = lazy(() => import("../platform/new/NewCheckPage"));
const ReportPage = lazy(() => import("../platform/report/ReportPage"));
const DemoPage = lazy(() => import("../demo/DemoPage"));
const LandingPage = lazy(() => import("../landing/LandingPage"));
const page = (el: JSX.Element) => <Suspense fallback={<p className="p-6 text-ink-2">{t("common.loading")}</p>}>{el}</Suspense>;

const ID_RE = /^[0-9a-f]{32}$/;
/** `/?check=<id>` links from the old interface. */
export function legacyRedirect(search: string): string | null {
  const id = new URLSearchParams(search).get("check");
  return id && ID_RE.test(id) ? `/app/checks/${id}` : null;
}

/** Supabase brings invitation / reset links back to "/" with the session (or an error) in the fragment. */
const AUTH_FRAGMENT = /(^|[#&])(access_token|error|error_code|type)=/;

function Root() {
  const loc = useLocation();
  // keep the fragment: /login reads it to show «Задайте пароль» or why the link failed
  if (AUTH_FRAGMENT.test(loc.hash)) return <Navigate to={{ pathname: "/login", hash: loc.hash }} replace />;
  const legacy = legacyRedirect(loc.search);
  if (legacy) return <Navigate to={legacy} replace />;
  return page(<LandingPage />);
}

const CHUNK_RELOAD_KEY = "tep.chunkReload";

/** A route failed to render. After a deploy the old lazy chunks are gone: reload once to get the new ones. */
export function RouteError({ error }: { error: unknown }) {
  const message = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : (error as Error)?.message ?? "";
  if (/dynamically imported module|Importing a module script failed/i.test(message)) {
    try {
      if (!sessionStorage.getItem(CHUNK_RELOAD_KEY)) { sessionStorage.setItem(CHUNK_RELOAD_KEY, "1"); location.reload(); return null; }
    } catch { /* storage blocked: show the screen */ }
  }
  return (
    <section role="alert" className="max-w-lg mx-auto my-[10vh] px-4 flex flex-col gap-3 items-start">
      <h1 className="text-xl font-semibold">{t("error.title")}</h1>
      <p className="text-ink-2 text-sm break-words">{message}</p>
      <Button variant="primary" onClick={() => location.reload()}>{t("error.reload")}</Button>
    </section>
  );
}
const RouteErrorElement = () => <RouteError error={useRouteError()} />;

export const routes: RouteObject[] = [
  { path: "/", element: <Root /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/demo", element: page(<DemoPage />), errorElement: <RouteErrorElement /> },
  {
    path: "/app",
    element: <RequireAuth><AppShell /></RequireAuth>,
    errorElement: <RouteErrorElement />,
    children: [
      { index: true, element: page(<ChecksPage />), errorElement: <RouteErrorElement /> },
      { path: "new", element: page(<NewCheckPage />), errorElement: <RouteErrorElement /> },
      { path: "checks/:id", element: page(<ReportPage />), errorElement: <RouteErrorElement /> },
      { path: "settings", element: <SettingsPage />, errorElement: <RouteErrorElement /> },
    ],
  },
  { path: "*", element: <Navigate to="/app" replace /> },
];
