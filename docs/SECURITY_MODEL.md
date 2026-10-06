# AttendAI — Security Model (as implemented)

## Authentication

* **Passwords**: scrypt (n=2^14, r=8, p=1, 16-byte random salt), constant-time comparison.
  An unknown email still runs a hash, so timing does not reveal which accounts exist. Both
  cases return the same `INVALID_CREDENTIALS` message.
* **Sessions**: 256-bit random token in an **httpOnly** cookie (`SameSite=Lax`, `Secure` in
  production, `Max-Age` = `SESSION_TTL_HOURS`, default 12). The database stores only
  `HMAC-SHA256(SECRET_KEY, token)`, so a database leak alone does not yield usable sessions.
  Sessions expire server-side, and **logout revokes the session**. Replaying the old cookie
  then fails (tested).
* **Android app tokens**: the same random session token is returned in the login body *only* when
  the request carries `X-AttendAI-Client: mobile`. The app stores it in app-private storage
  (Android backup disabled), sends it as `Authorization: Bearer`, and logout revokes it. Browsers
  never receive tokens in a response body, so the website's httpOnly-cookie protection is unchanged.
* **Throttling**: 8 failed logins per (client IP, email) per 15 minutes → `429`. In-process
  memory, bounded in size.
* `SECRET_KEY` is mandatory in production (startup fails if it is missing or shorter than
  32 characters).

## Authorization (server-side, every endpoint)

Implemented in `backend/app/authz.py`. List endpoints filter with an SQL scope condition, and
single-resource endpoints check the specific record. The frontend route guards are only for UX.

| Capability | STUDENT | MENTOR | ADMIN (HOD = department set) | EXAM_CELL |
|---|---|---|---|---|
| View a student's profile/attendance/analytics/condonations | **own only** | assigned students | all / own department | all (read-only) |
| Student lists, risk lists, overview | ✗ | assigned students | all / own department | all |
| Department report + CSV export | ✗ | ✗ | all / own department | all |
| Upload attendance | ✗ | ✗ | ✓ / own-department rows only | ✗ |
| Import history | ✗ | ✗ | all / own uploads | ✗ |
| Recompute analytics | ✗ | ✗ | ✓ (scoped) | ✗ |
| Submit / withdraw condonation | own | ✗ | ✗ | ✗ |
| Approve / reject condonation | ✗ (never own) | assigned students | all / own department | ✗ (view only) |
| Alerts | own | own | own | own |

Verified by `backend/tests/test_authorization.py`, `test_condonation.py`, the E2E suite
(student calls to `/api/students/1`, `/api/analytics/student/1` and a forged decision PATCH
all return 403), and an automated sweep of every OpenAPI route as anonymous (all 401) and as
a student with another student's ids.

## CSRF

Cookies are `SameSite=Lax`, and every state-changing `/api/*` request must carry
`X-Requested-With: AttendAI`. Browsers only send custom headers cross-origin after a CORS
preflight, and only configured origins pass that.

## CORS

The website needs no CORS (the API serves the SPA). The allow-list contains only the Android app's
WebView origins (`MOBILE_APP_ORIGINS`, default `https://localhost,capacitor://localhost`) plus any
explicit `CORS_ORIGINS` / `FRONTEND_ORIGIN` for split deployments. `*` is ignored, even if configured.
Allowing the app origin does not expose cookie sessions: cookies are `SameSite=Lax`, so they are not
sent on those cross-site requests, and the app authenticates with its own bearer token.

## Upload safety

* Extension allow-list (`.csv`, `.xlsx`; `.xls` and everything else → 415), magic-byte check
  (an XLSX must be a ZIP containing `xl/workbook.xml`; a "CSV" that is a ZIP is refused).
* Size limit enforced while streaming (`MAX_UPLOAD_MB`, default 5), row limit
  (`MAX_UPLOAD_ROWS`, default 20,000).
* Zip-bomb guard: total uncompressed size and entry count are checked before parsing.
  `defusedxml` is installed so openpyxl parses XML safely.
* Files are parsed in memory, never written to disk or executed. All values are read as text
  and validated (types, ranges, dates, references, scope). The stored filename is sanitised.
* Whole-file validation before any write. Rejected files leave the database unchanged.

## Injection and output safety

* SQL: SQLAlchemy ORM / bound parameters only. `LIKE` searches escape `%` and `_`.
* XSS: React escapes all output. No `dangerouslySetInnerHTML`. Strict CSP on the SPA:
  `default-src 'self'; script-src 'self'; frame-ancestors 'none'; …`.
* CSV export cells starting with `= + - @` (formula injection) are prefixed with `'`.

## Headers and transport

`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`,
`Permissions-Policy`, `Cache-Control: no-store` on API responses,
`Strict-Transport-Security` in production. HTTPS is terminated by the host (Render).

## Errors and logging

* Unhandled exceptions return a generic `INTERNAL_ERROR` with a request id. The stack trace is
  only logged server-side.
* Logs contain method, path (no query string), status, duration and request id, plus
  user id/role on login. They never contain passwords, tokens or uploaded content. The uvicorn
  access log is disabled. Client `X-Request-ID` values are accepted only if they match
  `[A-Za-z0-9._-]{1,64}`.
* API docs (`/api/docs`) are disabled in production.

## Secrets

Only environment variables. `.env` files are git-ignored, and `.env.example` documents the
names. Render generates `SECRET_KEY`. Demo accounts use a deliberately public password
(`DEMO_PASSWORD`) and exist only when demo seeding is enabled. Disable `SEED_DEMO_DATA` and
`DEMO_MODE` for a real institution.

## Dependency audit (2026-10-06)

`pip-audit -r backend/requirements.txt`: no known vulnerabilities.
`npm audit` (frontend): 0 vulnerabilities.

## Known limitations

* The login throttle is per process (resets on restart, not shared across workers or instances).
* `--forwarded-allow-ips` defaults to `*` so the client IP is taken from the host's proxy header.
  Behind a proxy that does not overwrite `X-Forwarded-For`, a client could vary the IP used in the
  throttle key. Set `FORWARDED_ALLOW_IPS` to the proxy's address where it is known.
* No password reset or account management UI (accounts are provisioned by seed or an administrator).
* No medical-document upload yet (`document_path` is reserved; P2 scope).
