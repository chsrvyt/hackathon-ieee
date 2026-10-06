import { expect, test, type Page } from "@playwright/test";
import { ACCOUNTS, login } from "./helpers";

/** Layout smoke test at phone (320/390), tablet (768) and desktop (1024/1440) widths. Read-only. */
const WIDTHS = [320, 390, 768, 1024, 1440];

async function checkLayout(page: Page, label: string) {
  await page.waitForLoadState("networkidle");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, `${label}: horizontal overflow`).toBeLessThanOrEqual(1);
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav, `${label}: navigation visible`).toBeVisible();
  // Touch targets on phones: primary controls in the page must be comfortably tappable.
  const width = page.viewportSize()!.width;
  if (width <= 400) {
    const small = await page.evaluate(() =>
      [...document.querySelectorAll("main button, main a.btn, main select, .bottomnav-link")]
        .map((el) => el.getBoundingClientRect())
        .filter((r) => r.width > 0 && r.height > 0 && r.height < 36).length,
    );
    expect(small, `${label}: controls smaller than 36px`).toBe(0);
  }
}

for (const width of WIDTHS) {
  test.describe(`${width}px`, () => {
    test.use({ viewport: { width, height: 900 } });

    test(`login, staff and student pages render at ${width}px`, async ({ page }) => {
      await page.goto("/login");
      await expect(page.getByLabel("Email")).toBeVisible();
      await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);

      await login(page, ACCOUNTS.admin);
      await expect(page.getByRole("heading", { name: "Admin dashboard" })).toBeVisible();
      await expect(page.locator(".stat").first()).toBeVisible();
      await checkLayout(page, "dashboard");
      await page.goto("/students");
      await expect(page.getByRole("link", { name: "Rohan Verma" })).toBeVisible();
      await checkLayout(page, "students");
      await page.getByRole("link", { name: "Rohan Verma" }).click();
      await expect(page.getByLabel("Why this risk level")).toBeVisible();
      await expect(page.locator("figure.chart svg")).toBeVisible(); // timeline chart renders
      await checkLayout(page, "student detail");
      await page.goto("/upload");
      await expect(page.getByTestId("file-input")).toBeAttached();
      await checkLayout(page, "upload");
      await page.goto("/reports");
      await expect(page.getByRole("heading", { name: /\(CSE\)/ })).toBeVisible();
      await checkLayout(page, "reports");
      await page.getByRole("button", { name: "Sign out" }).or(page.getByRole("button", { name: /^Account:/ })).first().click();
      const menuItem = page.getByRole("menuitem", { name: "Sign out" });
      if (await menuItem.isVisible()) await menuItem.click();
      await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();

      await login(page, ACCOUNTS.student);
      await expect(page.getByRole("heading", { name: "My attendance" })).toBeVisible();
      await checkLayout(page, "student home");
      await page.goto("/condonation");
      await expect(page.getByRole("heading", { name: "Condonation requests" })).toBeVisible();
      await checkLayout(page, "student requests");
    });
  });
}
