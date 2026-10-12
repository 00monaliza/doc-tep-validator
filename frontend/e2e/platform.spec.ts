import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../data/synthetic/samples/ru/ru_00001/text");

test("upload → sections → report → verdict → back to the list", async ({ page }) => {
  await page.goto("/app/new");
  await page.setInputFiles('input[type="file"]', ["PZ.pdf", "AR.pdf", "KR.pdf", "SMETA.pdf"].map(f => path.join(SAMPLE, f)));
  await expect(page.getByRole("heading", { name: "Проверьте разделы перед запуском" })).toBeVisible();
  await page.getByRole("button", { name: /Проверить 4/ }).click();
  await expect(page).toHaveURL(/\/app\/checks\/[0-9a-f]{32}$/);
  await expect(page.getByRole("heading", { name: "Общая площадь, м²" })).toBeVisible({ timeout: 30_000 });
  await page.keyboard.press("1");
  await expect(page.getByText("1/4")).toBeVisible();
  const id = page.url().split("/").pop()!;
  await page.getByRole("link", { name: "Проверки" }).click();
  // earlier runs leave their checks in data/uploads: find this check's own row
  const row = page.getByRole("row").filter({ has: page.locator(`a[href="/app/checks/${id}"]`) });
  await expect(row).toContainText("1/4");
});

test("old ?check= link opens the report", async ({ page, request }) => {
  const { id } = await (await request.post("http://localhost:8010/api/demo/ru")).json();
  await page.goto(`/?check=${id}`);
  await expect(page).toHaveURL(new RegExp(`/app/checks/${id}$`));
});

test("⌘K jumps to a check", async ({ page }) => {
  await page.goto("/app");
  await expect(page.getByRole("button", { name: /Поиск/ })).toBeVisible(); // the shell mounts after /api/capabilities
  await page.keyboard.press("Control+k");
  await page.getByPlaceholder("Найти проверку или замечание…").fill("Новая");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/app\/new$/);
});
