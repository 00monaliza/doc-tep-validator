import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import type { CheckRow } from "../../lib/types";
import ChecksTable from "./ChecksTable";

const row = (over: Partial<CheckRow> = {}): CheckRow => ({
  id: "a".repeat(32), title: "ЖК «Алатау», блок 2", status: "done", created_at: "2026-10-11T08:00:00+00:00",
  sections: ["PZ", "AR", "KR", "SMETA"], summary: { MISMATCH: 3, MISSING: 1, MATCH: 4 }, reviewed: 2,
  expires_at: "2026-10-18T08:00:00+00:00", ...over,
});
const show = (rows: CheckRow[], onRename = vi.fn()) =>
  render(<MemoryRouter><ChecksTable rows={rows} onRename={onRename} /></MemoryRouter>);

describe("checks table", () => {
  it("shows result, expert progress and missing sections", () => {
    show([row({ sections: ["PZ"] })]);
    const r = screen.getByRole("row", { name: /Алатау/ });
    expect(within(r).getByText("3 ≠")).toBeInTheDocument();
    expect(within(r).getByText("1 нет")).toBeInTheDocument();
    expect(within(r).getByText("2/4")).toBeInTheDocument();
    expect(within(r).getByText("АР")).toHaveAttribute("data-present", "false");
    expect(within(r).getByRole("link", { name: /Алатау/ })).toHaveAttribute("href", "/app/checks/" + "a".repeat(32));
  });

  it("shows status instead of a result while running or failed", () => {
    show([row({ id: "b".repeat(32), title: "Школа", status: "pending", summary: null }), row({ id: "c".repeat(32), title: "Котельная", status: "error", summary: null })]);
    expect(screen.getByText("идёт проверка…")).toBeInTheDocument();
    expect(screen.getByText("ошибка")).toBeInTheDocument();
  });

  it("long titles are cut with the full text in the tooltip", () => {  // Review Focus 3
    const long = "Көпқабатты тұрғын үй кешені ".repeat(8).trim();
    show([row({ title: long })]);
    const link = screen.getByRole("link", { name: long });
    expect(link).toHaveAttribute("title", long);
    expect(link.className).toMatch(/truncate/);
  });

  it("rename sends the new title", async () => {
    const onRename = vi.fn();
    show([row()], onRename);
    await userEvent.click(screen.getByRole("button", { name: "Переименовать" }));
    const input = screen.getByRole("textbox", { name: "Название" });
    await userEvent.clear(input);
    await userEvent.type(input, "Блок 2{Enter}");
    expect(onRename).toHaveBeenCalledWith("a".repeat(32), "Блок 2");
  });
});
