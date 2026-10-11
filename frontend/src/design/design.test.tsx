import { act, render, renderHook, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import Badge from "./Badge";
import Button from "./Button";
import SectionChip from "./SectionChip";
import StampSummary from "./StampSummary";
import { useTheme } from "./theme";

describe("design system", () => {
  beforeEach(() => { localStorage.clear(); document.documentElement.removeAttribute("data-theme"); });

  it("theme defaults to system and persists an explicit choice", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("system");
    act(() => result.current.setTheme("dark"));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("tep.theme")).toBe("dark");
  });

  it("badges always carry text, not only colour", () => {
    render(<Badge kind="mismatch">Расхождение</Badge>);
    expect(screen.getByText("Расхождение")).toHaveAttribute("data-kind", "mismatch");
  });

  it("section chip marks a missing section", () => {
    render(<SectionChip section="KR" present={false} />);
    const chip = screen.getByText("КР");
    expect(chip).toHaveAttribute("data-present", "false");
    expect(chip).toHaveAttribute("title", "Конструктивные решения: нет в пакете");
  });

  it("stamp summary renders every item with its tone", () => {
    render(<StampSummary items={[{ label: "Расхождения", value: "3", tone: "bad" }, { label: "Разделы", value: "4/4" }]} />);
    expect(screen.getByText("3").closest("[data-tone]")).toHaveAttribute("data-tone", "bad");
    expect(screen.getByText("4/4")).toBeInTheDocument();
  });

  it("primary button is a real button with type=button by default", () => {
    render(<Button variant="primary">Начать</Button>);
    expect(screen.getByRole("button", { name: "Начать" })).toHaveAttribute("type", "button");
  });
});
