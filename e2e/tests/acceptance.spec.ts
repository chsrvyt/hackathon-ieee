import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { ACCOUNTS, login, logout, trackConsole } from "./helpers";

const SAMPLE_CSV = fileURLToPath(new URL("../../sample_data/attendance_sample.csv", import.meta.url));
const INVALID_CSV = fileURLToPath(new URL("../../sample_data/attendance_invalid_example.csv", import.meta.url));

test.describe.configure({ mode: "serial" });

/** The visible main navigation: top bar on desktop, bottom tab bar on phones. */
const mainNav = (page: Page) => page.getByRole("navigation", { name: "Main navigation" });

test("health endpoint responds", async ({ request }) => {
  const res = await request.get("/health");
  expect(res.status()).toBe(200);
  expect(await res.json()).toEqual({ status: "ok" });
});

test("full judge demo flow: upload -> analytics -> mentor -> condonation -> report", async ({ page }) => {
  const errors = trackConsole(page);
  const stamp = `E2E ${new Date().toISOString()}`;

  await test.step("1-2. open the app and sign in as admin", async () => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
    await login(page, ACCOUNTS.admin);
    await expect(page.getByRole("heading", { name: "Admin dashboard" })).toBeVisible();
  });

  await test.step("3. invalid file is rejected with row-level errors and nothing saved", async () => {
    await page.getByRole("link", { name: "Upload attendance" }).first().click();
    await page.getByTestId("file-input").setInputFiles(INVALID_CSV);
    await page.getByRole("button", { name: "Upload and process" }).click();
    await expect(page.getByText("Upload rejected.")).toBeVisible();
    await expect(page.getByText(/Attendance cannot exceed conducted classes/)).toBeVisible();
    await expect(page.getByText(/Unknown student roll number 'S999'/)).toBeVisible();
  });

  await test.step("3-4. upload the sample attendance CSV and verify processing", async () => {
    await page.getByTestId("file-input").setInputFiles(SAMPLE_CSV);
    // Replace mode keeps the suite re-runnable against the same deployment.
    await page.getByRole("checkbox", { name: /Replace existing records/ }).check();
    await page.getByRole("button", { name: "Upload and process" }).click();
    await expect(page.getByText("Import successful.")).toBeVisible();
    await expect(page.getByText(/24 rows processed/)).toBeVisible();
    await expect(page.getByRole("cell", { name: "attendance_sample.csv" }).first()).toBeVisible();
  });

  await test.step("5-6. open analytics and find a critical student", async () => {
    await page.getByRole("link", { name: "Open dashboard" }).click();
    await expect(page.getByRole("heading", { name: "Admin dashboard" })).toBeVisible();
    await expect(page.locator(".stat").filter({ hasText: "Critical" })).toBeVisible();
    await page.goto("/students?risk=CRITICAL");
    const row = page.getByRole("row").filter({ hasText: "Rohan Verma" });
    await expect(row).toBeVisible();
    await expect(row).toContainText("CRITICAL");
    await row.getByRole("link", { name: "Rohan Verma" }).click();
  });

  await test.step("7-12. student detail: attendance, projection, risk, explanation, recovery", async () => {
    await expect(page.getByRole("heading", { name: "Rohan Verma" })).toBeVisible();
    const current = page.locator(".figure").filter({ hasText: "Current" });
    await expect(current).toContainText("74.5%"); // 108 / 145
    await expect(current).toContainText("108/145 classes");
    await expect(page.locator(".figure").filter({ hasText: "Projected" })).toContainText("72.8%");
    await expect(page.locator(".figure").filter({ hasText: "Target" })).toContainText("75%");
    await expect(page.getByLabel("Why this risk level")).toContainText("below the 75% target");
    await expect(page.getByText("CRITICAL").first()).toBeVisible();
    await expect(page.getByText(/Attend the next/).first()).toBeVisible();
    const recovery = page.getByRole("region", { name: "Recovery plan" });
    await expect(recovery).toContainText("3"); // (108+3)/(145+3) = 75.0 %
    await expect(recovery).toContainText("Recoverable");
    await expect(page.getByRole("heading", { name: "Subject-wise attendance" })).toBeVisible();
    await logout(page);
  });

  await test.step("14-16. mentor sees the at-risk student and pending condonation", async () => {
    await login(page, ACCOUNTS.mentor);
    await expect(page.getByRole("heading", { name: "Mentor dashboard" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Students needing attention" }).getByText("Rohan Verma")).toBeVisible();
    await page.getByRole("link", { name: /^Condonation/ }).click();
    await expect(page.getByRole("article").filter({ hasText: "Kabir Singh" }).first()).toBeVisible();
    await logout(page);
  });

  await test.step("17-19. student sees own dashboard and submits a condonation request", async () => {
    await login(page, ACCOUNTS.student);
    await expect(page.getByRole("heading", { name: "My attendance" })).toBeVisible();
    await expect(page.getByLabel("Why this risk level")).toBeVisible();
    await mainNav(page).getByRole("link", { name: "Condonation" }).click();
    await expect(page.getByRole("heading", { name: "Condonation requests" })).toBeVisible();
    // Keep re-runs clean: withdraw a leftover pending request from an earlier run.
    const leftover = page.getByRole("button", { name: "Withdraw request" });
    if (await leftover.count()) {
      await leftover.first().click();
      await expect(page.getByRole("button", { name: "Withdraw request" })).toHaveCount(0);
    }
    await page.getByLabel("Reason for absence").fill(`Hospitalised with dengue for twelve days in August. ${stamp}`);
    await page.getByRole("button", { name: "Submit condonation request" }).click();
    await expect(page.getByText(/Request submitted\. Status: PENDING/)).toBeVisible();
    await expect(page.getByRole("article").filter({ hasText: stamp }).getByText("PENDING", { exact: true })).toBeVisible();

    // Server-side authorization, not just hidden UI: another student's records are refused.
    expect((await page.request.get("/api/students/1")).status()).toBe(403);
    expect((await page.request.get("/api/analytics/student/1")).status()).toBe(403);
    const forged = await page.request.patch("/api/condonation/1/decision", {
      data: { decision: "APPROVED" },
      headers: { "X-Requested-With": "AttendAI" },
    });
    expect(forged.status()).toBe(403);
    await logout(page);
  });

  await test.step("20-21. mentor approves the request", async () => {
    await login(page, ACCOUNTS.mentor);
    await page.getByRole("link", { name: /^Condonation/ }).click();
    const card = page.getByRole("article").filter({ hasText: stamp });
    await card.getByRole("button", { name: "Approve" }).click();
    await page.getByLabel(/Comment/).fill(`Medical certificate verified. ${stamp}`);
    await page.getByRole("button", { name: "Approve request" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.getByRole("tab", { name: "Approved" }).click();
    await expect(page.getByRole("article").filter({ hasText: stamp }).getByText("APPROVED", { exact: true })).toBeVisible();
    await logout(page);
  });

  await test.step("22. student sees the decision and an alert", async () => {
    await login(page, ACCOUNTS.student);
    await expect(page.getByRole("heading", { name: "My attendance" })).toBeVisible();
    await expect(page.getByRole("region", { name: /Alerts/ }).getByText(/was approved by Prof\. Kavita Rao/).first()).toBeVisible();
    await mainNav(page).getByRole("link", { name: "Condonation" }).click();
    const card = page.getByRole("article").filter({ hasText: stamp });
    await expect(card.getByText("APPROVED", { exact: true })).toBeVisible();
    await expect(card).toContainText("Approved by Prof. Kavita Rao");
    await logout(page);
  });

  await test.step("23. department report with totals and CSV export", async () => {
    await login(page, ACCOUNTS.examCell);
    await expect(page.getByRole("heading", { name: "Exam Cell overview" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Upload attendance" })).toHaveCount(0);
    await page.getByRole("link", { name: "Department reports" }).first().click();
    await expect(page.getByRole("heading", { name: "Computer Science & Engineering (CSE)" })).toBeVisible();
    await expect(page.locator(".stat").filter({ hasText: "Total students" })).toContainText("8");
    await expect(page.getByRole("row").filter({ hasText: "Rohan Verma" })).toBeVisible();
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Export shortage list (CSV)" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("attendai_cse_shortage_report.csv");
    const csv = await readFile((await download.path())!, "utf8");
    expect(csv).toContain("roll_number");
    expect(csv).toContain("S003");
    await logout(page);
  });

  expect(errors, `browser console errors:\n${errors.join("\n")}`).toEqual([]);
});

test("HOD is limited to their department", async ({ page }) => {
  await login(page, ACCOUNTS.hodEce);
  await page.getByRole("link", { name: "Students", exact: true }).click();
  await expect(page.getByRole("row").filter({ hasText: "Karthik Reddy" })).toBeVisible();
  await expect(page.getByText("Rohan Verma")).toHaveCount(0);
  await page.goto("/students/3");
  await expect(page.getByText("Access denied")).toBeVisible();
});

test("phone layout: bottom navigation, no horizontal scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, ACCOUNTS.student);
  await expect(page.getByRole("heading", { name: "My attendance" })).toBeVisible();
  const tabs = mainNav(page);
  await expect(tabs.getByRole("link")).toHaveCount(3); // Home, Requests, Alerts
  for (const [tab, heading] of [["Requests", "Condonation requests"], ["Alerts", "Alerts"], ["Home", "My attendance"]]) {
    await tabs.getByRole("link", { name: tab }).click();
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `horizontal overflow on ${tab}`).toBeLessThanOrEqual(1);
  }
});

test("key pages have no WCAG 2.1 AA violations", async ({ page }) => {
  const scan = async (label: string) => {
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    const summary = result.violations.map((v) => `${label}: ${v.id} (${v.impact}) ${v.nodes[0]?.target}`);
    expect(summary).toEqual([]);
  };
  await page.goto("/login");
  await scan("login");
  await login(page, ACCOUNTS.admin);
  for (const path of ["/dashboard", "/students", "/students/3", "/upload", "/reports"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await scan(path);
  }
  await logout(page);
  await login(page, ACCOUNTS.student);
  await page.waitForLoadState("networkidle");
  await scan("/me");
});

test("unauthenticated API access and unknown routes are handled", async ({ request, page }) => {
  expect((await request.get("/api/analytics/overview")).status()).toBe(401);
  expect((await request.get("/api/nope")).status()).toBe(404);
  await page.goto("/definitely-not-a-page");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});
