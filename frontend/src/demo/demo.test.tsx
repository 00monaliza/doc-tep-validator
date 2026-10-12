import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { staticFileSource } from "../platform/report/fileSource";

describe("demo", () => {
  it("files of the demo come from static data, not the API (Review Focus 3)", async () => {
    expect(await staticFileSource("/demo-data")("x", "ПЗ.pdf")).toBe("/demo-data/files/%D0%9F%D0%97.pdf");
  });

  it("the demo report renders from static data and saves verdicts locally", async () => {
    const report = (await import("../../public/demo-data/report.json")).default;
    const calls: string[] = [];
    const origFetch = globalThis.fetch;
    globalThis.fetch = (async (u: RequestInfo | URL) => { calls.push(String(u)); return new Response(JSON.stringify(report)); }) as typeof fetch;
    const { default: DemoReport } = await import("./DemoReport");
    const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
    const { MemoryRouter } = await import("react-router");
    // ReportBody reads ?f= (⌘K jump to a finding), so it needs a router like on /demo
    render(<MemoryRouter><QueryClientProvider client={new QueryClient()}><DemoReport /></QueryClientProvider></MemoryRouter>);
    expect(await screen.findByRole("heading", { level: 2, name: "Общая площадь, м²" })).toBeInTheDocument();
    screen.getByRole("button", { name: /Подтверждаю/ }).click();
    expect(await screen.findByText("1/4")).toBeInTheDocument();
    expect(calls.filter(u => u.includes("/api/"))).toEqual([]);
    globalThis.fetch = origFetch;
  });
});
