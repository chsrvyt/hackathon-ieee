/**
 * Native (Android app) support. In a browser every function here is a no-op or returns the
 * web defaults, so the website keeps its same-origin, cookie-based behaviour.
 *
 * In the app the UI is bundled in the APK and talks to an AttendAI server chosen by the user
 * (default baked in at build time with VITE_DEFAULT_SERVER_URL). The app authenticates with a
 * bearer token kept in the app's private storage.
 */
import { Capacitor, SystemBars, SystemBarsStyle, SystemBarType } from "@capacitor/core";

const SERVER_KEY = "attendai.serverUrl";
const TOKEN_KEY = "attendai.token";

export const isNative = (): boolean => Capacitor.isNativePlatform();

export const DEFAULT_SERVER_URL = normalise((import.meta.env.VITE_DEFAULT_SERVER_URL as string | undefined) ?? "")
  .url ?? "";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: the session simply won't persist */
  }
}

/** Validate and canonicalise a server address typed by the user. */
export function normalise(input: string): { url?: string; error?: string } {
  let value = input.trim();
  if (!value) return { error: "Enter the AttendAI server address." };
  if (!/^[a-z]+:\/\//i.test(value)) value = `https://${value}`;
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return { error: "That is not a valid web address." };
  }
  const loopback = ["localhost", "127.0.0.1"].includes(parsed.hostname);
  if (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && loopback)) {
    return { error: "Use a secure https:// address." };
  }
  const path = parsed.pathname.replace(/\/+$/, "").replace(/\/api$/, "");
  return { url: `${parsed.origin}${path}` };
}

export function getServerUrl(): string {
  return read(SERVER_KEY) || DEFAULT_SERVER_URL;
}

export function setServerUrl(url: string) {
  write(SERVER_KEY, url);
}

export function getToken(): string | null {
  return read(TOKEN_KEY);
}

export function setToken(token: string | null) {
  write(TOKEN_KEY, token);
}

/** Probe a server's /health endpoint (used before saving a server address). */
export async function checkServer(url: string): Promise<boolean> {
  try {
    const res = await fetch(`${url}/health`, { credentials: "omit" });
    const body = await res.json();
    return res.ok && body?.status === "ok";
  } catch {
    return false;
  }
}

/** Save text as a file in the app cache and open the Android share sheet ("Save to Files", Drive, email...). */
export async function shareTextFile(filename: string, text: string, title: string) {
  const [{ Filesystem, Directory, Encoding }, { Share }] = await Promise.all([
    import("@capacitor/filesystem"),
    import("@capacitor/share"),
  ]);
  const written = await Filesystem.writeFile({
    path: filename,
    data: text,
    directory: Directory.Cache,
    encoding: Encoding.UTF8,
  });
  await Share.share({ title, files: [written.uri], dialogTitle: title });
}

/** Wire Android hardware back button and system bar styling. Call once at startup. */
export async function initNativeShell(goBack: () => void, canGoBack: () => boolean) {
  if (!isNative()) return;
  try {
    const { App } = await import("@capacitor/app");
    await App.addListener("backButton", () => {
      if (canGoBack()) goBack();
      else void App.exitApp();
    });
  } catch {
    /* App plugin unavailable: Android falls back to its default back behaviour */
  }
  try {
    // Light icons on the navy top bar, dark icons above the white bottom tab bar.
    await SystemBars.setStyle({ style: SystemBarsStyle.Dark, bar: SystemBarType.StatusBar });
    await SystemBars.setStyle({ style: SystemBarsStyle.Light, bar: SystemBarType.NavigationBar });
  } catch {
    /* older WebView / platform without SystemBars support */
  }
}
