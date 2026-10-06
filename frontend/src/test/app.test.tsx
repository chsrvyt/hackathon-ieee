import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../api/client";
import App from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { CondonationForm } from "../components/Condonation";
import { StudentAnalyticsView } from "../components/StudentAnalyticsView";
import { RiskBadge } from "../components/ui";
import { analyticsFixture } from "./fixtures";

type Handler = (url: string, init: RequestInit) => { status?: number; body: unknown };
let handler: Handler;
const calls: { url: string; init: RequestInit }[] = [];

beforeEach(() => {
  calls.length = 0;
  handler = (url) => {
    if (url.endsWith("/auth/session")) return { body: { user: null } };
    if (url.endsWith("/auth/demo-accounts")) return { body: { enabled: false, accounts: [] } };
    if (url.includes("/analytics/recovery")) return { body: { ...analyticsFixture().recovery, current_percentage: 74.48 } };
    return { status: 404, body: { error: { code: "NOT_FOUND", message: "nope", details: [] } } };
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      const { status = 200, body } = handler(url, init);
      return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());

function wrap(ui: ReactNode, route = "/") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("api client", () => {
  it("sends the CSRF header and credentials on state-changing requests", async () => {
    handler = () => ({ body: { ok: true } });
    await api("/x", { json: { a: 1 } });
    const init = calls[0].init;
    expect((init.headers as Record<string, string>)["X-Requested-With"]).toBe("AttendAI");
    expect(init.credentials).toBe("include");
    expect(init.method).toBe("POST");
  });

  it("maps the error contract to ApiError", async () => {
    handler = () => ({
      status: 422,
      body: { error: { code: "VALIDATION_ERROR", message: "Attendance cannot exceed conducted classes.", details: [] } },
    });
    const err = (await api("/x").catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("VALIDATION_ERROR");
    expect(err.message).toBe("Attendance cannot exceed conducted classes.");
  });

  it("reports network failures clearly", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    const err = (await api("/x").catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("NETWORK_ERROR");
  });
});

describe("routing and auth", () => {
  it("redirects unauthenticated users to the login page", async () => {
    wrap(<App />, "/dashboard");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("shows the server's message on failed login", async () => {
    handler = (url) => {
      if (url.endsWith("/auth/session")) return { body: { user: null } };
      if (url.endsWith("/auth/demo-accounts")) return { body: { enabled: false, accounts: [] } };
      return { status: 401, body: { error: { code: "INVALID_CREDENTIALS", message: "Incorrect email or password." } } };
    };
    wrap(<App />, "/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Email"), "student@attendai.demo");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
  });

  it("signs in and lands on the role's home page", async () => {
    const admin = { id: 1, name: "Dr. Neha Kapoor", email: "admin@attendai.demo", role: "ADMIN", department: null, student_id: null };
    handler = (url) => {
      if (url.endsWith("/auth/session")) return { body: { user: null } };
      if (url.endsWith("/auth/demo-accounts")) return { body: { enabled: false, accounts: [] } };
      if (url.endsWith("/auth/login")) return { body: { user: admin } };
      if (url.endsWith("/alerts")) return { body: { items: [], unread_count: 0 } };
      if (url.endsWith("/analytics/overview")) return { status: 500, body: { error: { code: "X", message: "stub" } } };
      return { status: 404, body: { error: { code: "NOT_FOUND", message: "nope" } } };
    };
    wrap(<App />, "/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Email"), "admin@attendai.demo");
    await user.type(screen.getByLabelText("Password"), "Demo@2026");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Dr. Neha Kapoor")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Sign in" })).not.toBeInTheDocument();
  });

  it("keeps students out of staff pages", async () => {
    handler = (url) => {
      if (url.endsWith("/auth/session"))
        return {
          body: {
            user: { id: 6, name: "Rohan Verma", email: "s", role: "STUDENT", department: null, student_id: 3 },
          },
        };
      if (url.includes("/analytics/student/3")) return { body: analyticsFixture() };
      if (url.includes("/alerts")) return { body: { items: [], unread_count: 0 } };
      if (url.includes("/condonation/student/3")) return { body: { items: [] } };
      if (url.includes("/analytics/recovery")) return { body: { ...analyticsFixture().recovery, current_percentage: 74.48 } };
      return { status: 403, body: { error: { code: "FORBIDDEN", message: "no" } } };
    };
    wrap(<App />, "/upload");
    expect(await screen.findByRole("heading", { name: "My attendance" })).toBeInTheDocument();
    expect(screen.queryByText("Upload attendance")).not.toBeInTheDocument();
  });
});

describe("explainable analytics view", () => {
  it("shows current, projected, target, reason, action and recovery", async () => {
    wrap(<StudentAnalyticsView data={analyticsFixture()} audience="student" />);
    expect(screen.getByText("74.5%")).toBeInTheDocument();
    expect(screen.getAllByText("72.8%").length).toBeGreaterThan(0);
    expect(screen.getAllByText(analyticsFixture().reason).length).toBeGreaterThan(0);
    expect(screen.getAllByText(analyticsFixture().recommended_action).length).toBeGreaterThan(0);
    expect(screen.getByText("Recoverable")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Attendance 74.5% against a 75% target/ })).toBeInTheDocument();
  });

  it("renders an empty state when no classes are recorded", () => {
    const fx = analyticsFixture();
    wrap(<StudentAnalyticsView data={{ ...fx, overall: { ...fx.overall, classes_conducted: 0 } }} audience="staff" />);
    expect(screen.getByText("No attendance recorded yet")).toBeInTheDocument();
  });
});

describe("components", () => {
  it("risk badges carry text, not only colour", () => {
    render(
      <>
        <RiskBadge level="CRITICAL" />
        <RiskBadge level="WARNING" />
        <RiskBadge level="SAFE" />
      </>,
    );
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();
    expect(screen.getByText("WARNING")).toBeInTheDocument();
    expect(screen.getByText("SAFE")).toBeInTheDocument();
  });

  it("condonation form only opens for at-risk students and enforces a minimum reason", async () => {
    const { unmount } = wrap(<CondonationForm analytics={analyticsFixture({ risk_level: "SAFE" })} />);
    expect(screen.getByText(/You are currently on track/)).toBeInTheDocument();
    unmount();
    wrap(<CondonationForm analytics={analyticsFixture()} />);
    const submit = screen.getByRole("button", { name: "Submit condonation request" });
    expect(submit).toBeDisabled();
    await userEvent.setup().type(screen.getByLabelText("Reason for absence"), "Hospitalised with dengue in August.");
    await waitFor(() => expect(submit).toBeEnabled());
  });
});
