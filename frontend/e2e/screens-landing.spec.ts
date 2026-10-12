// Screenshots of the landing for the manual check (plan 2, Task 7). Run: npx playwright test screens-landing
import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../test-results/screens");

test("landing screens", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.waitForTimeout(1500); // scene chunk
  const how = await page.evaluate(() => { const r = document.getElementById("how")!.getBoundingClientRect(); return r.bottom + scrollY - innerHeight; });
  for (const [name, share] of [["start", 0], ["middle", 0.5], ["end", 0.95]] as const) {
    await page.evaluate(y => scrollTo(0, y), Math.round(how * share));
    await page.waitForTimeout(700);
    await page.screenshot({ path: `${OUT}/landing-1366-${name}.png` });
  }
  for (const id of ["example", "checks", "research", "access"]) {
    await page.locator(`#${id}`).scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${OUT}/landing-1366-${id}.png` });
  }
  await page.evaluate(() => scrollTo(0, 0));
  await page.getByRole("button", { name: "KZ" }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/landing-1366-kz.png` });
  await page.getByRole("button", { name: "RU" }).click();
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.reload();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/landing-375-dark.png`, fullPage: true });
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/demo");
  await expect(page.getByRole("heading", { level: 2, name: "Общая площадь, м²" })).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/demo-1920.png` });
});
