import { Unauthorized } from "../lib/api";
import { toLogin } from "../lib/queries";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { legacyRedirect, routes } from "./router";
import { SessionContext, type Session } from "./providers";

const session = (over: Partial<Session> = {}): Session => ({
  ready: true, enabled: true, email: null, ocr: true, signOut: vi.fn(), refresh: vi.fn(), ...over,
});

function at(path: string, s: Session) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<SessionContext.Provider value={s}><RouterProvider router={router} /></SessionContext.Provider>);
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