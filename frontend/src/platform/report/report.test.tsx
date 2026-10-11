import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Finding, Review } from "../../lib/types";
import FindingDetail from "./FindingDetail";
import FindingsColumn from "./FindingsColumn";
import { NO_FILTER } from "./findings";
import { reportState } from "./ReportPage";

const f = (over: Partial<Finding> = {}): Finding => ({
  type: "AREA_PZ_VS_AR_EXPLICATION", field: "total_area_m2", verdict: "MISMATCH", notes: ["экспликация без лестничных клеток"],
  refs: [{ section: "PZ", value: 1247.79, page: 1 }, { section: "AR", value: 1382, page: 2 }], delta_rel: -0.097, ...over,
});
const none: Review = { verdict: null, comment: "" };

describe("finding detail", () => {
  it("shows both values, the difference and the notes", () => {
    render(<FindingDetail finding={f()} review={none} onReview={vi.fn()} saving={false} />);
    // ru-RU numbers use a no-break space between thousands: match any space
    expect(screen.getByText(/^1\s247,79$/)).toBeInTheDocument();
    expect(screen.getByText(/^1\s382$/)).toBeInTheDocument();
    expect(screen.getByText("−9,7 %")).toBeInTheDocument();
    expect(screen.getByText("экспликация без лестничных клеток")).toBeInTheDocument();
  });

  it("one place or three places: every value, no difference row (Review Focus 1)", () => {
    const three = f({ refs: [{ section: "PZ", value: 10, page: 1 }, { section: "PZ", value: 12, page: 2 }, { section: "PZ", value: 11, page: 3 }], delta_rel: null });
    render(<FindingDetail finding={three} review={none} onReview={vi.fn()} saving={false} />);
    expect(screen.getAllByRole("row")).toHaveLength(3);
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it("nothing selected: an empty state (Review Focus 4)", () => {
    render(<FindingDetail finding={null} review={none} onReview={vi.fn()} saving={false} />);
    expect(screen.getByText("Выберите замечание слева")).toBeInTheDocument();
  });

  it("verdict buttons send the review", () => {
    const onReview = vi.fn();
    render(<FindingDetail finding={f()} review={none} onReview={onReview} saving={false} />);
    screen.getByRole("button", { name: /Подтверждаю/ }).click();
    expect(onReview).toHaveBeenCalledWith({ verdict: "confirmed", comment: "" });
  });
});

describe("report page state (Review Focus 2)", () => {
  it("maps every status to something the user can read", () => {
    expect(reportState(undefined, null)).toEqual({ kind: "loading" });
    expect(reportState({ id: "x", status: "pending" }, null)).toEqual({ kind: "message", text: "Идёт проверка документов…" });
    expect(reportState({ id: "x", status: "receiving" }, null).kind).toBe("message");
    expect(reportState({ id: "x", status: "error", error: "boom" }, null)).toEqual({ kind: "message", text: "Проверка не выполнена: boom", error: true });
    expect(reportState({ id: "x", status: "uploaded", files: {} }, null)).toEqual({ kind: "redirect", to: "/app/new?id=x" });
    expect(reportState(undefined, new Error("Проверка не найдена"))).toEqual({ kind: "message", text: "Проверка не найдена или удалена.", error: true });
  });
});

describe("findings column", () => {
  const report = (findings: Finding[]) => ({
    lang: "ru", documents: [], findings, summary: { MISMATCH: 0, MISSING: 1, MATCH: 0 },
    completeness: { required: [], present: [], missing: [], unrecognised: [], duplicates: [] }, tep: {},
  });
  const props = (findings: Finding[]) => ({
    report: report(findings), bad: findings.filter(x => x.verdict !== "MATCH"), ok: findings.filter(x => x.verdict === "MATCH"),
    filter: NO_FILTER, onFilter: vi.fn(), matchesOpen: false, onMatchesOpen: vi.fn(), current: null, onPick: vi.fn(),
    reviewOf: () => undefined, onPickRefs: vi.fn(),
  });

  it("a finding with one place renders without the missing second value (Review Focus 1)", () => {
    const one = f({ verdict: "MISSING", refs: [{ section: "SMETA", value: 741922.828, page: 1 }], delta_rel: null });
    render(<FindingsColumn {...props([one])} />);
    expect(screen.getByRole("button", { name: /Общая площадь/ })).toBeInTheDocument();
  });

  it("no findings: says so instead of an empty list (Review Focus 4)", () => {
    render(<FindingsColumn {...props([])} />);
    expect(screen.getByText("Расхождений между разделами не найдено.")).toBeInTheDocument();
  });
});
