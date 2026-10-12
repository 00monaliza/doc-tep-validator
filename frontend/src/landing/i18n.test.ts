import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { KZ, RU, useLang } from "./i18n";

describe("landing languages (Review Focus 5)", () => {
  beforeEach(() => localStorage.clear());

  it("Kazakh has every key of Russian and no empty text", () => {
    expect(Object.keys(KZ).sort()).toEqual(Object.keys(RU).sort());
    expect(Object.entries(KZ).filter(([, v]) => !v.trim())).toEqual([]);
  });

  it("the choice switches texts, is remembered and sets <html lang>", () => {
    const { result } = renderHook(() => useLang());
    expect(result.current.tl("hero.demo")).toBe(RU["hero.demo"]);
    act(() => result.current.setLang("kz"));
    expect(result.current.tl("hero.demo")).toBe(KZ["hero.demo"]);
    expect(localStorage.getItem("tep.lang")).toBe("kz");
    expect(document.documentElement.lang).toBe("kk");
    expect(renderHook(() => useLang()).result.current.lang).toBe("kz");
  });
});
