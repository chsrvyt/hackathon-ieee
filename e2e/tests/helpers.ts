import { expect, type Page } from "@playwright/test";

export const PASSWORD = process.env.DEMO_PASSWORD ?? "Demo@2026";
export const ACCOUNTS = {
  admin: "admin@attendai.demo",
  mentor: "mentor@attendai.demo",
  student: "student@attendai.demo",
  examCell: "examcell@attendai.demo",
  hodEce: "hod.ece@attendai.demo",
};

/**
 * Collect application errors: uncaught exceptions, console.error from app code and any 5xx response.
 * Chromium's own "Failed to load resource" lines are skipped because expected 4xx responses
 * (e.g. the deliberate 422 for an invalid upload) are correct behaviour, not defects.
 */
export function trackConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().startsWith("Failed to load resource")) {
      errors.push(`${page.url()} :: ${m.text()}`);
    }
  });
  page.on("pageerror", (e) => errors.push(`pageerror :: ${e.message}`));
  page.on("response", (r) => r.status() >= 500 && errors.push(`HTTP ${r.status()} :: ${r.url()}`));
  return errors;
}

export async function login(page: Page, email: string) {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

export async function logout(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
}
