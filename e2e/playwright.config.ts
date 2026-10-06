import { defineConfig, devices } from "@playwright/test";

/**
 * E2E acceptance suite. Point it at any running AttendAI deployment:
 *   E2E_BASE_URL=https://attendai.onrender.com npx playwright test
 * CHROMIUM_PATH lets sandboxes reuse a preinstalled Chromium instead of downloading one.
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
