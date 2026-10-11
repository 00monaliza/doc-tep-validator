import { describe, expect, it } from "vitest";
import type { CheckRow, Report } from "../../lib/types";
import { buildCommands } from "./commands";

const check = { id: "a".repeat(32), title: "ЖК «Алатау»" } as CheckRow;
const report = { findings: [{ field: "total_area_m2", verdict: "MISMATCH" }, { field: "floors", verdict: "MATCH" }] } as unknown as Report;

describe("command menu", () => {
  it("offers actions, checks and — inside a report — its findings", () => {
    const cmds = buildCommands({ checks: [check], report, checkId: "a".repeat(32), theme: "light", canSignOut: true });
    expect(cmds.filter(c => c.group === "Действия").map(c => c.label)).toEqual(["Новая проверка", "Скачать XLSX", "Переключить тему", "Выйти"]);
    expect(cmds.find(c => c.group === "Проверки")).toMatchObject({ label: "ЖК «Алатау»", run: { type: "go", to: "/app/checks/" + "a".repeat(32) } });
    expect(cmds.filter(c => c.group === "Замечания").map(c => c.label)).toEqual(["Общая площадь, м²"]);
  });

  it("outside a report there is no export and no findings; without login no sign-out", () => {
    const cmds = buildCommands({ checks: [], report: null, checkId: null, theme: "dark", canSignOut: false });
    expect(cmds.map(c => c.label)).toEqual(["Новая проверка", "Переключить тему"]);
  });
});
