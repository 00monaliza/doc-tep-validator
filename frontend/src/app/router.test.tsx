import { Unauthorized } from "../lib/api";
import { toLogin } from "../lib/queries";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { legacyRedirect, RouteError, routes } from "./router";
import { SessionContext, type Session } from "./providers";

vi.mock("../landing/LandingPage", () => ({ default: () => <h1>landing</h1> }));

const session = (over: Partial<Session> = {}): Session => ({
  ready: true, enabled: true, email: null, ocr: true, signOut: vi.fn(), refresh: vi.fn(), ...over,
});

function at(path: string, s: Session) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  // the app gets a QueryClient from Providers; the shell's ⌘K needs one
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <SessionContext.Provider value={s}><RouterProvider router={router} /></SessionContext.Provider>
    </QueryClientProvider>,
  );
  return router;
}

describe("routes", () => {
  it("old ?check= links open the report", () => {
    expect(legacyRedirect("?check=" + "a".repeat(32))).toBe("/app/checks/" + "a".repeat(32));
    expect(legacyRedirect("?check=../etc")).toBeNull();
    expect(legacyRedirect("")).toBeNull();
  });

  it("signed-out user is sent to login with the way back", async () => {
    const router = at("/app/checks/" + "b".repeat(32), session());
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(router.state.location.search).toBe("?next=" + encodeURIComponent("/app/checks/" + "b".repeat(32)));
  });

  it("without auth (local run) the app opens directly", async () => {
    at("/app/settings", session({ enabled: false }));
    expect(await screen.findByRole("heading", { name: "Настройки" })).toBeInTheDocument();
  });
});

it("a 401 anywhere sends the user to login and back", () => {
  const assign = vi.fn();
  vi.stubGlobal("location", { ...location, pathname: "/app/checks/" + "c".repeat(32), search: "", assign });
  toLogin(new Unauthorized("x"));
  expect(assign).toHaveBeenCalledWith("/login?next=" + encodeURIComponent("/app/checks/" + "c".repeat(32)));
  toLogin(new Error("not auth"));
  expect(assign).toHaveBeenCalledTimes(1);
  vi.unstubAllGlobals();
});
describe("email links and errors", () => {
  it("an invitation or reset link on / goes to /login with its fragment intact (Final 1)", async () => {
    const router = at("/#access_token=x&type=invite", session());
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(router.state.location.hash).toBe("#access_token=x&type=invite");
  });

  it("an expired-link error on / also goes to /login", async () => {
    const router = at("/#error=access_denied&error_code=otp_expired", session());
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });

  it("every app route has an error screen (Final 4)", () => {
    const app = routes.find(r => r.path === "/app")!;
    expect(app.errorElement).toBeTruthy();
  });

  it("the error screen offers a reload", () => {
    render(<RouteError error={new Error("boom")} />);
    expect(screen.getByRole("button", { name: "Обновить страницу" })).toBeInTheDocument();
  });
});

it("/ shows the landing, links from emails still go to /login (Review Focus 1)", async () => {
  at("/", session());
  expect(await screen.findByRole("heading", { name: "landing" })).toBeInTheDocument();
  const router = at("/#access_token=x&type=recovery", session());
  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
});
