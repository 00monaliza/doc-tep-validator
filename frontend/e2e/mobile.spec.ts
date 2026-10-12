import { expect, test, type Page } from "@playwright/test";

// the page scrolls inside <main>, so both the document and <main> must fit the screen width
const noSideScroll = (page: Page) => page.evaluate(() => {
  const main = document.querySelector("main")!;
  return document.documentElement.scrollWidth <= window.innerWidth && main.scrollWidth <= main.clientWidth + 1;
});
const fits = async (page: Page, name: RegExp) => {
  const box = await page.getByRole("button", { name }).first().boundingBox();
  return box !== null && box.x >= 0 && box.x + box.width <= 375 + 1;
};

test.use({ viewport: { width: 375, height: 812 } });

test("on a phone the list and the report fit the screen and the menu opens", async ({ page, request }) => {
  const { id } = await (await request.post("http://localhost:8010/api/demo/ru")).json();
  await expect.poll(async () => (await (await request.get(`http://localhost:8010/api/checks/${id}`)).json()).status, { timeout: 30_000 }).toBe("done");

  await page.goto("/app");
  await expect(page.getByRole("heading", { name: /Мои проверки/ })).toBeVisible();
  expect(await noSideScroll(page)).toBe(true);
  await expect(page.getByRole("navigation", { name: "Разделы" })).toBeHidden();
  await page.getByRole("button", { name: "Меню" }).click();
  await expect(page.getByRole("link", { name: "Настройки" })).toBeVisible();

  await page.goto(`/app/checks/${id}`);
  await expect(page.getByRole("heading", { level: 2 })).toBeVisible({ timeout: 20_000 });
  expect(await noSideScroll(page)).toBe(true);
  expect(await fits(page, /Общая площадь/)).toBe(true);
  expect(await fits(page, /Подтверждаю/)).toBe(true);
  await expect(page.getByRole("navigation", { name: "Разделы" })).toBeHidden();
});
