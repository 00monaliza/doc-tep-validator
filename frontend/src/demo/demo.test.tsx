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
    globalThis.fetch = (async (u: RequestInfo | URL) => {
      calls.push(String(u));
      await new Promise(r => setTimeout(r, calls.length * 20)); // the second answer comes later, after the first render
      return new Response(JSON.stringify(report));
    }) as typeof fetch;
    const { default: DemoReport } = await import("./DemoReport");
    const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
    const { MemoryRouter } = await import("react-router");
    // ReportBody reads ?f= (⌘K jump to a finding), so it needs a router like on /demo
    const { StrictMode } = await import("react");
    // StrictMode runs the loading effect twice: the report arrives as two objects (the dev server does this too)
    render(<StrictMode><MemoryRouter><QueryClientProvider client={new QueryClient()}><DemoReport /></QueryClientProvider></MemoryRouter></StrictMode>);
    expect(await screen.findByRole("heading", { level: 2, name: "Общая площадь, м²" })).toBeInTheDocument();
    screen.getByRole("button", { name: /Подтверждаю/ }).click();
    expect(await screen.findByText("1/4")).toBeInTheDocument();
    expect(calls.filter(u => u.includes("/api/"))).toEqual([]);
    globalThis.fetch = origFetch;
  });
});

describe("demo inside the landing", () => {
  it("the embedded report does not add a second <h1> to the page", async () => {
    const { ReportBody } = await import("../platform/report/ReportPage");
    const report = (await import("../../public/demo-data/report.json")).default;
    const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
    const { MemoryRouter } = await import("react-router");
    render(<MemoryRouter><QueryClientProvider client={new QueryClient()}>
      <ReportBody checkId="x" report={report as never} title="Демо" initial={{}} titleLevel={3} />
    </QueryClientProvider></MemoryRouter>);
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    expect(screen.getByRole("heading", { level: 3, name: "Демо" })).toBeInTheDocument();
  });
});
