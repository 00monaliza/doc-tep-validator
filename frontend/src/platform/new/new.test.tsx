import { describe, expect, it } from "vitest";
import { reduceWizard, type WizardState } from "./NewCheckPage";

describe("new check wizard", () => {
  it("goes files → uploading → sections → running", () => {
    let s: WizardState = { step: "files" };
    s = reduceWizard(s, { type: "upload", total: 10 });
    expect(s).toEqual({ step: "uploading", sent: 0, total: 10 });
    s = reduceWizard(s, { type: "progress", sent: 4 });
    expect(s).toEqual({ step: "uploading", sent: 4, total: 10 });
    s = reduceWizard(s, { type: "uploaded", id: "x", files: {} });
    expect(s.step).toBe("sections");
    s = reduceWizard(s, { type: "start" });
    expect(s).toEqual({ step: "running", id: "x" });
  });

  it("progress outside uploading and start outside sections are ignored", () => {
    const files: WizardState = { step: "files" };
    expect(reduceWizard(files, { type: "progress", sent: 3 })).toBe(files);
    expect(reduceWizard(files, { type: "start" })).toBe(files);
  });

  it("a failure is shown and reset returns to files", () => {
    const s = reduceWizard({ step: "uploading", sent: 1, total: 2 }, { type: "fail", message: "сеть" });
    expect(s).toEqual({ step: "failed", message: "сеть" });
    expect(reduceWizard(s, { type: "reset" })).toEqual({ step: "files" });
  });
});
