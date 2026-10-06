/**
 * Thin fetch wrapper. Auth is an httpOnly session cookie (never readable from JS);
 * every state-changing call carries the X-Requested-With header the backend requires.
 */

const RAW_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";
export const API_BASE = RAW_BASE.replace(/\/+$/, "");

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
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? (options.json !== undefined || options.form ? "POST" : "GET");
  const headers: Record<string, string> = { Accept: "application/json" };
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
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body,
      credentials: "include",
      signal: options.signal,
    });
  } catch (err) {
    if ((err as Error)?.name === "AbortError") throw err;
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
    if (response.status === 401 && !options.silent401) unauthorizedListeners.forEach((l) => l());
    throw apiError;
  }
  return data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
