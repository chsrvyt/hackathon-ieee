# AttendAI — Final Status

**Project:** AttendAI — Attendance Shortage Early Warning & Condonation System
**Date:** 2026-10-06 (live deployment verification) · **Branch:** `claude/lucid-mccarthy-05cpem`

## Deployment

| Item | Value |
|---|---|
| Status | **LIVE** on Render |
| Website (frontend) | https://attendai-gjk1.onrender.com |
| Backend API | https://attendai-gjk1.onrender.com/api (same origin as the website) |
| Health | https://attendai-gjk1.onrender.com/health → `{"status":"ok"}` (verified 2026-10-06) |
| Database | Render managed PostgreSQL 16 (`attendai-db`, private network only) |
| Provider / config | Render Blueprint [`render.yaml`](../render.yaml), deploys the `main` branch |
| Deployment date | 2026-10-06 |
| Android app | APK 1.0.6, opens connected to the live URL: https://github.com/chsrvyt/hackathon-ieee/releases/tag/android-latest |

## Live verification (run on the public URL against the production database)

Run: [Live verification #1](https://github.com/chsrvyt/hackathon-ieee/actions/runs/37451206519),
2026-10-06 10:55 UTC, Playwright from GitHub's runners with `E2E_PRODUCTION=1`.
Result: **18 passed, 1 failed, 1 skipped** (app-mode browser test, which needs a second origin;
the Android emulator test covers it).

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | `/health` | PASS | `{"status":"ok"}` on the first request |
| 2 | Frontend loads | PASS | SPA served, sign-in page renders |
| 3 | Admin login | PASS | `admin@attendai.demo` |
| 4 | Attendance CSV upload | PASS | invalid file rejected with row errors and nothing saved; `attendance_sample.csv` imported |
| 5 | Analytics | PASS | dashboard totals and risk distribution |
| 6 | Critical student | PASS | Rohan Verma listed under CRITICAL |
| 7 | Risk explanation | PASS | 74.5% (108/145), projected 72.8% vs target 75%, reason shown |
| 8 | Recovery calculator | PASS | 3 consecutive classes, "Recoverable" |
| 9 | Mentor login | PASS | `mentor@attendai.demo`, at-risk students and pending requests |
| 10 | Student login | PASS | `student@attendai.demo`, own dashboard only |
| 11 | Condonation submission | PASS | student submits a request |
| 12 | Condonation approval | PASS | mentor approves; a student's self-approval attempt gets 403 |
| 13 | Student status update | PASS | student sees APPROVED and an alert |
| 14 | Department report | PASS | Exam Cell CSE report |
| 15 | CSV export | PASS | `attendai_cse_shortage_report.csv` downloaded |
| 16 | Cross-student authorization | PASS | 403 for another student's profile, analytics, attendance and condonation; 403 for staff endpoints; mentor/HOD blocked from other departments |
| 17 | Mobile layout | **FAIL at 320 px**, PASS at 390/768/1024/1440 px | 320 px admin dashboard scrolled sideways by 17 px (histogram labels). Phone bottom navigation and touch targets PASS |
| 18 | Production CORS / errors | PASS | foreign origin gets no CORS header, app origin allowed; generic 401/403/422 without internals; CSRF enforced; Secure+HttpOnly cookie, HSTS, CSP, no `/api/docs` |
| – | WCAG 2.1 AA (axe) | PASS | key pages |
| – | Frontend bundle secrets scan | PASS | no keys, connection strings or private keys |

### The 320 px failure

The version Render was serving did not yet contain the fix (histogram columns `minmax(0, 1fr)`
with wrapping labels). That fix passed at 320 px locally, on the Render-style container and in
CI. [PR #2](https://github.com/chsrvyt/hackathon-ieee/pull/2) merged it into `main` on
2026-10-06, which triggers a Render redeploy. **Re-verification on the public URL is pending**:
the **Live verification** workflow run for that push waits until Render serves the new commit
(`GET /api/version`) and then repeats the whole suite.

## Android app

| Check | Result |
|---|---|
| Build | APK 1.0.6, signed, 3.8 MB ([Android run #6](https://github.com/chsrvyt/hackathon-ieee/actions/runs/37451206363)) |
| Emulator (Android 15) | PASS: no native action bar, opens with `Server: attendai-gjk1.onrender.com`, student and admin flows, back button, 0 px overflow |
| Against the live HTTPS server | Not run yet (the live workflow's Android job runs after the web job passes) |
| HTTPS only | The app refuses non-HTTPS servers except device loopback |

Fixed in 1.0.6: the action bar with a squashed splash image at the top of the first screen,
the "Sign in" heading on the server step (an email was typed as the server address), and the
stretched login layout on phones.

## Tests

| Suite | Result |
|---|---|
| Backend (unit + API on PostgreSQL) | **183 passed** |
| Frontend | **11 passed** |
| E2E in CI | **20 passed** ([CI run #15](https://github.com/chsrvyt/hackathon-ieee/actions/runs/37451206386), `APP_ENV=production`): demo flow, HOD scope, phone navigation, WCAG, errors, app mode, 8 security checks, 5 layout widths |
| Render-style container (local) | 19 passed on a fresh database and on a re-run |
| Docker image | builds in CI |

## Production configuration

| Check | Result |
|---|---|
| `DATABASE_URL` | from the Render database; no public access |
| `SECRET_KEY` | generated by Render; production refuses a missing or short key |
| CORS | same-origin website; only `https://localhost` and `capacitor://localhost` (app) allowed cross-origin; verified live |
| Debug | off: no `/api/docs`, generic 500s, no reload (verified live) |
| Migrations / seed | `alembic upgrade head` on start; idempotent demo seed |
| Secrets in git | none (`.env` ignored; only the public demo password and CI's dummy key appear) |

## Acceptance gates

| Gate | Status |
|---|---|
| 1–16 Build, tests, database, auth, authorization, upload, calculations, projection, explanation, recovery, dashboards, condonation, reports, production build | PASS |
| 17 Deployment | PASS: live on Render |
| 18 LIVE frontend | PASS |
| 19 LIVE backend | PASS |
| 20 LIVE end-to-end demo | PASS for every functional flow; mobile 320 px FAIL until the merged fix is re-verified live |

## Demo credentials

Password `Demo@2026` for every account (fictional data, public by design, seeded only when
`SEED_DEMO_DATA=true`):

| Email | Role |
|---|---|
| `admin@attendai.demo` | Admin, all departments |
| `hod.ece@attendai.demo` | HOD, ECE only |
| `mentor@attendai.demo` | Mentor, CSE students |
| `mentor.ece@attendai.demo` | Mentor, ECE students |
| `examcell@attendai.demo` | Exam Cell (read-only reports) |
| `student@attendai.demo` | Student Rohan Verma (S003) |

## Known limitations

- Projections assume the recent rate continues; no timetable/holiday modelling, no claimed accuracy.
- Not an examination-eligibility ruling (institutional rules are not encoded).
- No admin UI for subjects/roster (imports can register new ones); no password reset; login throttle is per process.
- Render free tier: the service sleeps after 15 idle minutes (first request about 30–60 s); free PostgreSQL expires after 30 days.
- APKs use a per-build signing key until `ANDROID_KEYSTORE_*` secrets are set, so updates need an uninstall first.
- The live demo flow changes demo data the way a judge would (re-imports the sample, approves Rohan's request).

## Final verdict

```text
LIVE: https://attendai-gjk1.onrender.com (Render + PostgreSQL)
All functional flows PASS on the public URL (login, upload, analytics, risk, recovery,
condonation, reports, authorization, CORS/errors).
One check failed on the public URL: 320 px dashboard overflow. The fix is merged (PR #2) and the
Live verification workflow re-tests once Render serves it. Not yet re-verified live.
```
