import { expect, test } from "@playwright/test";

test("landing → demo without login, and no request to the API (Review Focus 3)", async ({ page }) => {
  const api: string[] = [];
  page.on("request", r => { if (r.url().includes("/api/") && !r.url().endsWith("/api/capabilities")) api.push(r.url()); });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Сверка");
  await page.getByRole("link", { name: "Попробовать демо" }).first().click();
  await expect(page).toHaveURL(/\/demo$/);
  await expect(page.getByRole("heading", { level: 2, name: "Общая площадь, м²" })).toBeVisible({ timeout: 20_000 });
  // the key handler attaches right after the first paint: a harmless click first, as a person would
  await page.getByRole("heading", { level: 2, name: "Общая площадь, м²" }).click();
  await page.keyboard.press("1");
  await expect(page.getByText("1/4")).toBeVisible();
  expect(api).toEqual([]);
});

test("KZ is remembered after reload (Review Focus 5)", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "KZ" }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "kk");
});

test.describe("phone and reduced motion (Review Focus 4)", () => {
  test.use({ viewport: { width: 375, height: 812 }, reducedMotion: "reduce" });
  test("fallback frames, no side scroll", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("canvas")).toHaveCount(0);
    await expect(page.locator('svg[data-scene="fallback"]:visible')).toHaveCount(1); // the wide-screen column is hidden
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
});

test("access request is accepted", async ({ page }) => {
  await page.goto("/#access");
  await page.getByLabel("Почта").fill(`e2e-${Date.now()}@bureau.kz`);
  await page.getByLabel("Организация").fill("ТОО «Бюро»");
  await page.getByRole("button", { name: "Отправить заявку" }).click();
  await expect(page.getByText(/Спасибо! Заявка отправлена/)).toBeVisible();
});

test("the landing stays on its first screen, and the embedded demo loads when it comes near", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("heading", { level: 1 }).waitFor();
  await page.waitForTimeout(1500);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.locator("#example").scrollIntoViewIfNeeded();
  await expect(page.locator("#example").getByRole("heading", { level: 3 })).toBeVisible();
});

test("«Запросить доступ» on the demo page leads to the form", async ({ page }) => {
  await page.goto("/demo");
  await page.getByRole("link", { name: "Запросить доступ" }).click();
  await expect(page.locator("#access form")).toBeInViewport();
});
