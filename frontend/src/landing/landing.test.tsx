import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SessionContext, type Session } from "../app/providers";
import { CHECK_TYPES, FACTS, METRICS } from "./content";
import { KZ, RU } from "./i18n";
import LandingPage from "./LandingPage";

vi.mock("../demo/DemoReport", () => ({ default: () => <div>demo report</div> }));

const session = (over: Partial<Session> = {}): Session => ({
  ready: true, enabled: true, email: null, ocr: true, signOut: vi.fn(), refresh: vi.fn(), ...over,
});
const show = (s = session()) =>
  render(<SessionContext.Provider value={s}><MemoryRouter><LandingPage /></MemoryRouter></SessionContext.Provider>);

describe("landing", () => {
  beforeEach(() => localStorage.clear());

  it("has the nine blocks in order", () => {
    show();
    const titles = screen.getAllByRole("heading", { level: 2 }).map(h => h.textContent);
    expect(titles).toEqual([RU["problem.title"], RU["how.title"], RU["example.title"], RU["checks.title"],
      RU["langs.title"], RU["research.title"], RU["security.title"], RU["access.title"]]);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(RU["hero.title"]);
  });

  it("facts and metrics come from content.ts", () => {
    show();
    const research = within(document.getElementById("research")!);
    expect(research.getByText(METRICS.extraction.ru)).toBeInTheDocument();
    expect(research.getByText(METRICS.real.tep)).toBeInTheDocument();
    expect(within(document.getElementById("checks")!).getAllByRole("listitem")).toHaveLength(CHECK_TYPES.length);
    expect(screen.getByText(RU["security.retention"].replace("{n}", String(FACTS.retentionDays)))).toBeInTheDocument();
  });

  it("signed out: «Войти» (Review Focus 1)", () => {
    show();
    expect(screen.getAllByRole("link", { name: RU["nav.login"] })[0]).toHaveAttribute("href", "/login");
  });

  it("signed in: «Открыть платформу» instead of «Войти» (Review Focus 1)", () => {
    show(session({ email: "a@b.kz" }));
    expect(screen.getAllByRole("link", { name: RU["nav.open"] })[0]).toHaveAttribute("href", "/app");
    expect(screen.queryByRole("link", { name: RU["nav.login"] })).toBeNull();
  });

  it("the language switch turns the whole page Kazakh", () => {
    show();
    screen.getByRole("button", { name: "KZ" }).click();
    return screen.findByRole("heading", { level: 1, name: KZ["hero.title"] });
  });
});

describe("landing: review fixes", () => {
  beforeEach(() => localStorage.clear());

  it("the embedded demo (pdf.js, PDFs) loads only when block 04 comes near, not with the first screen", () => {
    show(); // the test IntersectionObserver never reports the block as visible
    expect(screen.queryByText("demo report")).toBeNull();
  });

  it("/#access from the demo page scrolls to the form once the lazy landing is drawn", () => {
    const spy = vi.fn();
    Element.prototype.scrollIntoView = spy;
    render(<SessionContext.Provider value={session()}><MemoryRouter initialEntries={["/#access"]}><LandingPage /></MemoryRouter></SessionContext.Provider>);
    expect(spy).toHaveBeenCalled();
    expect(spy.mock.contexts[0]).toBe(document.getElementById("access"));
  });

  it("leaving the landing in KZ gives the platform back <html lang=ru>", () => {
    localStorage.setItem("tep.lang", "kz");
    const { unmount } = show();
    expect(document.documentElement.lang).toBe("kk");
    unmount();
    expect(document.documentElement.lang).toBe("ru");
  });
});
