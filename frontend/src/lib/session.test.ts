import { describe, expect, it, vi } from "vitest";

vi.mock("./auth", () => ({ accessToken: vi.fn(), signOutLocal: vi.fn() }));
import { Unauthorized } from "./api";
import { signOutLocal } from "./auth";
import { toLogin, withReview } from "./queries";

describe("expired sessions (Final 7)", () => {
  it("a 401 ends the local session before going to login, so /login cannot bounce back", () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...location, pathname: "/app", search: "", assign });
    toLogin(new Unauthorized("x"));
    expect(signOutLocal).toHaveBeenCalled();
    expect(assign).toHaveBeenCalledWith("/login?next=%2Fapp");
    vi.unstubAllGlobals();
  });
});

describe("check cache after a verdict (Final 6)", () => {
  it("withReview puts the saved verdict into the cached check, removing an empty one", () => {
    const data = { id: "x", status: "done" as const, report: {} as never, reviews: { "1": { verdict: "confirmed" as const, comment: "" } } };
    const a = withReview(data, 0, { verdict: "false_positive", comment: "нет" });
    expect(a.reviews).toEqual({ "0": { verdict: "false_positive", comment: "нет" }, "1": { verdict: "confirmed", comment: "" } });
    expect(withReview(a, 1, { verdict: null, comment: "" }).reviews).toEqual({ "0": { verdict: "false_positive", comment: "нет" } });
  });
});
