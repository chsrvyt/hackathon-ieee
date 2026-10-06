import { expect, request as playwrightRequest, test, type APIRequestContext } from "@playwright/test";
import { ACCOUNTS, PASSWORD } from "./helpers";

/**
 * Non-destructive security checks, safe to run against a live deployment.
 * E2E_PRODUCTION=1 additionally asserts production hardening (Secure cookie, HSTS, no API docs).
 */
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8080";
const PRODUCTION = process.env.E2E_PRODUCTION === "1";
const CSRF = { "X-Requested-With": "AttendAI" };
const NO_INTERNALS = /Traceback|File "|sqlalchemy|psycopg|\/app\/backend/i;

async function signedIn(email: string): Promise<APIRequestContext> {
  const ctx = await playwrightRequest.newContext({ baseURL: BASE });
  const r = await ctx.post("/api/auth/login", { data: { email, password: PASSWORD }, headers: CSRF });
  expect(r.status(), `login ${email}`).toBe(200);
  return ctx;
}

async function studentIdByRoll(admin: APIRequestContext, roll: string): Promise<number> {
  const r = await admin.get(`/api/students?search=${roll}`);
  const item = (await r.json()).items.find((s: { roll_number: string }) => s.roll_number === roll);
  expect(item, `student ${roll} exists`).toBeTruthy();
  return item.id;
}

test("unauthenticated API access is rejected without leaking internals", async ({ request }) => {
  for (const path of ["/api/students", "/api/analytics/overview", "/api/auth/me", "/api/alerts", "/api/condonation/pending"]) {
    const r = await request.get(path);
    expect(r.status(), path).toBe(401);
    const body = await r.text();
    expect(body).not.toMatch(NO_INTERNALS);
    expect(JSON.parse(body).error.code).toBe("UNAUTHENTICATED");
  }
});

test("students can only read their own records", async () => {
  const admin = await signedIn(ACCOUNTS.admin);
  const other = await studentIdByRoll(admin, "S001");
  const student = await signedIn(ACCOUNTS.student);
  const own = (await (await student.get("/api/auth/me")).json()).user.student_id;
  expect(own).not.toBe(other);
  for (const path of [`/api/students/${other}`, `/api/analytics/student/${other}`, `/api/attendance/student/${other}`, `/api/condonation/student/${other}`]) {
    expect((await student.get(path)).status(), path).toBe(403);
  }
  expect((await student.get(`/api/analytics/student/${own}`)).status()).toBe(200);
  for (const path of ["/api/students", "/api/analytics/overview", "/api/condonation/pending"]) {
    expect((await student.get(path)).status(), path).toBe(403);
  }
});

test("students cannot approve condonation requests", async () => {
  const mentor = await signedIn(ACCOUNTS.mentor);
  const pending = (await (await mentor.get("/api/condonation/pending")).json()).items;
  expect(pending.length, "a pending request exists (seeded)").toBeGreaterThan(0);
  const student = await signedIn(ACCOUNTS.student);
  const r = await student.patch(`/api/condonation/${pending[0].id}/decision`, {
    data: { decision: "APPROVED", comment: "self-approval attempt" },
    headers: CSRF,
  });
  expect(r.status()).toBe(403);
  const after = (await (await mentor.get("/api/condonation/pending")).json()).items.map((x: { id: number }) => x.id);
  expect(after).toContain(pending[0].id); // still pending
});

test("mentors and HODs cannot read other departments", async () => {
  const admin = await signedIn(ACCOUNTS.admin);
  const ece = await studentIdByRoll(admin, "E001");
  const cse = await studentIdByRoll(admin, "S003");
  const mentor = await signedIn(ACCOUNTS.mentor); // CSE mentor
  expect((await mentor.get(`/api/students/${ece}`)).status()).toBe(403);
  expect((await mentor.get(`/api/analytics/student/${ece}`)).status()).toBe(403);
  const hod = await signedIn(ACCOUNTS.hodEce);
  expect((await hod.get(`/api/students/${cse}`)).status()).toBe(403);
  const depts = (await (await hod.get("/api/departments")).json()).items.map((d: { code: string }) => d.code);
  expect(depts).toEqual(["ECE"]);
});

test("uploads are validated and rejected files change nothing", async () => {
  const admin = await signedIn(ACCOUNTS.admin);
  const upload = (name: string, body: string) =>
    admin.post("/api/attendance/upload", {
      headers: CSRF,
      multipart: { file: { name, mimeType: "text/plain", buffer: Buffer.from(body) }, dry_run: "true" },
    });
  const wrongType = await upload("notes.txt", "hello");
  expect(wrongType.status()).toBe(415);
  const bad = await upload(
    "bad.csv",
    "student_roll,subject_code,date,classes_conducted,classes_attended\nS001,CS101,2026-09-01,10,12\n",
  );
  expect(bad.status()).toBe(422);
  const body = await bad.json();
  expect(body.success).toBe(false);
  expect(body.rows_processed).toBe(0);
  expect(body.errors[0].message).toContain("cannot exceed conducted");
  expect(JSON.stringify(body)).not.toMatch(NO_INTERNALS);
});

test("errors are generic and CORS only admits the app origins", async ({ request }) => {
  const malformed = await request.post("/api/auth/login", {
    headers: { ...CSRF, "Content-Type": "application/json" },
    data: "{not json",
  });
  expect(malformed.status()).toBe(422);
  expect(await malformed.text()).not.toMatch(NO_INTERNALS);
  const noCsrf = await request.post("/api/auth/logout");
  expect(noCsrf.status()).toBe(403);

  const preflight = (origin: string) =>
    request.fetch("/api/auth/login", {
      method: "OPTIONS",
      headers: { Origin: origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type" },
    });
  expect((await preflight("https://evil.example")).headers()["access-control-allow-origin"]).toBeUndefined();
  expect((await preflight("https://localhost")).headers()["access-control-allow-origin"]).toBe("https://localhost");
});

test("the shipped frontend bundle contains no secrets", async ({ request }) => {
  const html = await (await request.get("/")).text();
  const scripts = [...html.matchAll(/src="(\/assets\/[^"]+\.js)"/g)].map((m) => m[1]);
  expect(scripts.length).toBeGreaterThan(0);
  for (const src of scripts) {
    const js = await (await request.get(src)).text();
    expect(js, src).not.toMatch(/SECRET_KEY|DATABASE_URL|postgres(ql)?:\/\/|BEGIN [A-Z ]*PRIVATE KEY|ci-only-not-a-secret/);
  }
});

test("production hardening", async ({ request }) => {
  test.skip(!PRODUCTION, "set E2E_PRODUCTION=1 when targeting a production deployment");
  expect((await request.get("/api/docs")).status()).toBe(404);
  expect((await request.get("/api/openapi.json")).status()).toBe(404);
  const login = await request.post("/api/auth/login", {
    data: { email: ACCOUNTS.examCell, password: PASSWORD },
    headers: CSRF,
  });
  const cookie = login.headers()["set-cookie"] ?? "";
  expect(cookie).toContain("HttpOnly");
  expect(cookie).toContain("Secure");
  expect(cookie.toLowerCase()).toContain("samesite=lax");
  const page = await request.get("/");
  expect(page.headers()["strict-transport-security"]).toContain("max-age=");
  expect(page.headers()["content-security-policy"]).toContain("frame-ancestors 'none'");
});
