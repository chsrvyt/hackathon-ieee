import { expect, test } from "@playwright/test";
import { ACCOUNTS, PASSWORD } from "./helpers";

/**
 * Android-app code path, exercised in Chromium: the built SPA is served from a separate origin
 * (like the APK's https://localhost WebView), Capacitor is told it runs on Android by the
 * `androidBridge` global it looks for, and the app must work cross-origin with bearer tokens.
 *
 *   E2E_NATIVE_URL = origin serving frontend/dist (listed in the API's MOBILE_APP_ORIGINS)
 *   E2E_API_URL    = API server the "app" connects to
 */
const NATIVE_URL = process.env.E2E_NATIVE_URL;
const API_URL = process.env.E2E_API_URL ?? process.env.E2E_BASE_URL ?? "http://localhost:8000";

test.skip(!NATIVE_URL, "set E2E_NATIVE_URL to run the app-mode tests");
test.use({ viewport: { width: 390, height: 844 }, baseURL: NATIVE_URL });

test.beforeEach(async ({ context }) => {
  await context.addInitScript(() => {
    (window as unknown as { androidBridge: unknown }).androidBridge = { postMessage: () => undefined };
  });
});

test("app: choose server, sign in with a bearer token, navigate, sign out", async ({ page, context, request }) => {
  const appErrors: string[] = [];
  page.on("pageerror", (e) => appErrors.push(e.message));
  await page.goto("/");

  await test.step("server picker validates and checks the address", async () => {
    await expect(page.getByRole("heading", { name: "Connect to your institution" })).toBeVisible();
    await expect(page.getByLabel("Email")).toHaveCount(0); // no sign-in until a server is chosen
    const address = page.getByLabel("Server address");
    await address.fill("http://insecure.example.com");
    await page.getByRole("button", { name: "Connect" }).click();
    await expect(page.getByRole("alert")).toContainText("https://");
    await address.fill(API_URL);
    await page.getByRole("button", { name: "Connect" }).click();
    await expect(page.getByText(`Server: ${API_URL.replace(/^https?:\/\//, "")}`)).toBeVisible();
  });

  await test.step("sign in uses a bearer token, not cookies", async () => {
    await page.getByLabel("Email").fill(ACCOUNTS.student);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("heading", { name: "My attendance" })).toBeVisible();
    await expect(page.locator(".figure").filter({ hasText: "Current" })).toContainText("%");
    const token = await page.evaluate(() => localStorage.getItem("attendai.token"));
    expect(token).toBeTruthy();
    expect(await context.cookies(API_URL)).toEqual([]);
    const me = await request.get(`${API_URL}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
    expect(me.status()).toBe(200);
  });

  await test.step("bottom tab bar navigation", async () => {
    const tabs = page.getByRole("navigation", { name: "Main navigation" });
    await tabs.getByRole("link", { name: "Requests" }).click();
    await expect(page.getByRole("heading", { name: "Condonation requests" })).toBeVisible();
    await tabs.getByRole("link", { name: "Alerts" }).click();
    await expect(page.getByRole("heading", { name: "Alerts", exact: true })).toBeVisible();
  });

  await test.step("sign out revokes the token", async () => {
    const token = await page.evaluate(() => localStorage.getItem("attendai.token"));
    await page.getByRole("button", { name: /^Account:/ }).click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
    expect(await page.evaluate(() => localStorage.getItem("attendai.token"))).toBeNull();
    const after = await request.get(`${API_URL}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
    expect(after.status()).toBe(401);
  });

  expect(appErrors).toEqual([]);
});
