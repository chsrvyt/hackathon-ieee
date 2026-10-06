/**
 * Thin fetch wrapper. On the web, auth is an httpOnly session cookie (never readable from JS).
 * In the Android app, auth is a bearer token sent to the configured server (see native.ts).
 * Every state-changing call carries the X-Requested-With header the backend requires.
 */
import { getServerUrl, getToken, isNative, setToken, shareTextFile } from "../native";

const RAW_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";
export const API_BASE = RAW_BASE.replace(/\/+$/, "");

/** Base URL for API calls: same-origin "/api" on the web, the chosen server in the app. */
export function apiBase(): string {
  return isNative() ? `${getServerUrl()}/api` : API_BASE;
}

export interface ErrorDetail {
  row?: number | null;
  column?: string | null;
  value?: string | null;
  field?: string | null;
  message: string;
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: ErrorDetail[];
  body: unknown;

  constructor(status: number, code: string, message: string, details: ErrorDetail[] = [], body: unknown = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.body = body;
  }
}

type Listener = () => void;
const unauthorizedListeners = new Set<Listener>();

/** Called when any request reports an expired/missing session. */
export function onUnauthorized(listener: Listener): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  json?: unknown;
  form?: FormData;
  signal?: AbortSignal;
  /** Do not broadcast 401s (used by the initial "who am I" probe and login). */
  silent401?: boolean;
  headers?: Record<string, string>;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? (options.json !== undefined || options.form ? "POST" : "GET");
  const native = isNative();
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  const token = native ? getToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  } else if (options.form) {
    body = options.form;
  }
  if (method !== "GET") headers["X-Requested-With"] = "AttendAI";

  let response: Response;
  try {
    if (native && !getServerUrl()) {
      throw new ApiError(0, "NO_SERVER", "Choose the AttendAI server first.");
    }
    response = await fetch(`${apiBase()}${path}`, {
      method,
      headers,
      body,
      credentials: native ? "omit" : "include",
      signal: options.signal,
    });
  } catch (err) {
    if ((err as Error)?.name === "AbortError" || err instanceof ApiError) throw err;
    throw new ApiError(0, "NETWORK_ERROR", "Cannot reach the AttendAI server. Check your connection and try again.");
  }

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!response.ok) {
    const err = (data as { error?: { code?: string; message?: string; details?: ErrorDetail[] } } | null)?.error;
    const apiError = new ApiError(
      response.status,
      err?.code ?? `HTTP_${response.status}`,
      err?.message ?? `Request failed (${response.status}).`,
      Array.isArray(err?.details) ? err!.details : [],
      data,
    );
    if (response.status === 401) {
      if (native) setToken(null);
      if (!options.silent401) unauthorizedListeners.forEach((l) => l());
    }
    throw apiError;
  }
  return data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

/**
 * Download a file produced by the API (CSV template, department export).
 * Web: a normal link navigation (cookie auth). App: fetch with the token, then the share sheet.
 */
export async function downloadFile(path: string, filename: string, title: string): Promise<void> {
  if (!isNative()) {
    const a = document.createElement("a");
    a.href = `${apiBase()}${path}`;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    return;
  }
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${apiBase()}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: "omit",
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Cannot reach the AttendAI server.");
  }
  if (!res.ok) throw new ApiError(res.status, `HTTP_${res.status}`, `Download failed (${res.status}).`);
  await shareTextFile(filename, await res.text(), title);
}
