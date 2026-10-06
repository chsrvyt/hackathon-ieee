/**
 * On-device smoke test for the AttendAI APK (debug build, WebView debugging enabled).
 * Requires a running emulator/device with the APK installed and the API reachable from the
 * device at APP_SERVER_URL (CI uses `adb reverse tcp:8000 tcp:8000` → http://localhost:8000).
 */
import fs from "node:fs";
import { _android as android } from "@playwright/test";

const PKG = "com.attendai.app";
const SERVER = process.env.APP_SERVER_URL ?? "http://localhost:8000";
const OUT = process.env.SCREENSHOT_DIR ?? "android-screenshots";
const PASSWORD = process.env.DEMO_PASSWORD ?? "Demo@2026";
fs.mkdirSync(OUT, { recursive: true });

const [device] = await android.devices();
if (!device) throw new Error("No Android device/emulator connected");
console.log(`device: ${device.model()} (${device.serial()})`);

const errors = [];
const shot = (name) => device.screenshot({ path: `${OUT}/${name}.png` });

await device.shell(`pm clear ${PKG}`); // fresh install state
await device.shell(`am start -W -n ${PKG}/.MainActivity`);
const webview = await device.webView({ pkg: PKG }, { timeout: 90_000 });
const page = await webview.page();
page.on("pageerror", (e) => errors.push(e.message));
page.setDefaultTimeout(45_000);

async function signIn(email) {
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}
const tabs = () => page.getByRole("navigation", { name: "Main navigation" });

// 0. No native action bar or title strip above the web UI (the WebView fills the window)
const ui = (await device.shell("uiautomator dump /sdcard/attendai-ui.xml >/dev/null; cat /sdcard/attendai-ui.xml")).toString();
if (!ui.includes("<hierarchy")) console.log("uiautomator dump unavailable; action bar check skipped");
else if (/resource-id="[^"]*:id\/(action_bar|action_bar_container|action_bar_title|title)"/.test(ui))
  throw new Error("a native action bar is visible above the app");
else console.log("no native action bar");

// 1. First launch: server picker, or the server baked into this build (then switch to SERVER)
const picker = page.getByRole("heading", { name: "Connect to your institution" });
const chip = page.getByText(/^Server:/);
await picker.or(chip).first().waitFor({ timeout: 90_000 });
await shot("01-first-launch-server");
if (await chip.isVisible()) {
  console.log(`preconfigured ${await chip.innerText()}`);
  await page.getByRole("button", { name: "Change" }).click();
}
await page.getByLabel("Server address").fill(SERVER);
await page.getByRole("button", { name: "Connect" }).click();
await page.getByText(/^Server:/).waitFor();
await shot("02-sign-in");

// 2. Student: dashboard, explanation, tabs, Android back button
await signIn("student@attendai.demo");
await page.getByRole("heading", { name: "My attendance" }).waitFor();
await page.getByLabel("Why this risk level").waitFor();
const current = await page.locator(".figure").filter({ hasText: "Current" }).innerText();
if (!/%/.test(current)) throw new Error(`no attendance figure rendered: ${current}`);
await shot("03-student-home");
await tabs().getByRole("link", { name: "Requests" }).click();
await page.getByRole("heading", { name: "Condonation requests" }).waitFor();
await shot("04-student-requests");
await device.shell("input keyevent 4"); // hardware back
await page.getByRole("heading", { name: "My attendance" }).waitFor();

// Layout sanity on the real device: no horizontal overflow, bottom bar above the gesture area.
const layout = await page.evaluate(() => {
  const nav = document.querySelector(".bottomnav")?.getBoundingClientRect();
  const top = document.querySelector(".topbar")?.getBoundingClientRect();
  const css = getComputedStyle(document.documentElement);
  return {
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    viewport: [window.innerWidth, window.innerHeight],
    bottomNavBottom: nav ? Math.round(nav.bottom) : null,
    topBarHeight: top ? Math.round(top.height) : null,
    safeTop: css.getPropertyValue("--safe-area-inset-top").trim(),
    safeBottom: css.getPropertyValue("--safe-area-inset-bottom").trim(),
  };
});
console.log("layout:", JSON.stringify(layout));
if (layout.overflow > 1) throw new Error(`horizontal overflow ${layout.overflow}px`);
if (!layout.bottomNavBottom || layout.bottomNavBottom > layout.viewport[1] + 1) throw new Error("bottom bar off-screen");

// 3. Sign out through the account menu, then admin dashboard
await page.getByRole("button", { name: /^Account:/ }).click();
await page.getByRole("menuitem", { name: "Sign out" }).click();
await page.getByRole("heading", { name: "Sign in" }).waitFor();
await signIn("admin@attendai.demo");
await page.getByRole("heading", { name: "Admin dashboard" }).waitFor();
await page.locator(".stat").filter({ hasText: "Critical" }).waitFor();
await shot("05-admin-dashboard");
await tabs().getByRole("link", { name: "Students" }).click();
await page.getByRole("heading", { name: "Students" }).waitFor();
await page.getByText("Rohan Verma").first().waitFor();
await shot("06-admin-students");

await device.close();
if (errors.length) throw new Error(`page errors: ${errors.join("; ")}`);
console.log("APP SMOKE TEST PASSED");
