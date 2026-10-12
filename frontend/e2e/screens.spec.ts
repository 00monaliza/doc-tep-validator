// Screenshots for the manual check (plan Task 9): 375 / 1366 / 1920 px, light and dark. Run: npx playwright test screens
import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../test-results/screens");

test("screens", async ({ page, request }) => {
  test.setTimeout(120_000);
  const { id } = await (await request.post("http://localhost:8010/api/demo/ru")).json();
  await expect.poll(async () => (await (await request.get(`http://localhost:8010/api/checks/${id}`)).json()).status, { timeout: 30_000 }).toBe("done");
  await request.patch(`http://localhost:8010/api/checks/${id}`, { data: { title: "Көпқабатты тұрғын үй кешені ".repeat(7).trim().slice(0, 200) } });
  for (const theme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    for (const [w, h] of [[375, 812], [1366, 768], [1920, 1080]] as const) {
      await page.setViewportSize({ width: w, height: h });
      await page.goto("/app");
      await expect(page.getByRole("heading", { name: /Мои проверки/ })).toBeVisible();
      await page.screenshot({ path: `${OUT}/${theme}-${w}-list.png` });
      await page.goto(`/app/checks/${id}`);
      await expect(page.getByRole("heading", { level: 2 })).toBeVisible({ timeout: 20_000 });
      await page.waitForTimeout(1500); // PDF page render
      await page.screenshot({ path: `${OUT}/${theme}-${w}-report.png` });
    }
  }
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/app/new");
  await page.screenshot({ path: `${OUT}/light-1366-new.png` });
});
