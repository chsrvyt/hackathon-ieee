# AttendAI — QA Test Plan and Coverage

Every planned check is automated. Counts are from the last local run (2026-10-06).

| Suite | Command | Result |
|---|---|---|
| Backend unit + integration (real PostgreSQL) | `cd backend && pytest` | **181 passed** |
| Backend lint/format | `ruff check app tests && ruff format --check app tests` | clean |
| Frontend typecheck + unit | `cd frontend && npx tsc -b && npx vitest run` | **11 passed** |
| Frontend production build | `npx vite build` | OK (109 KB gzipped JS) |
| E2E (production Docker image + PostgreSQL) | `cd e2e && npx playwright test` | **7 passed** (acceptance flow, HOD scope, phone layout, WCAG 2.1 AA, errors, app mode), on a fresh database and on re-runs |
| UI/UX audit (all roles, 360/390/768/1024/1440 px) | Playwright + axe-core script | 0 overflow, 0 touch targets < 36 px on phones, 0 WCAG 2.1 AA violations, 0 JS errors |
| Android app on emulator | `.github/workflows/android.yml` → `e2e/android/app-smoke.mjs` | see the Android workflow run and the `android-latest` release notes |
| Dependency audit | `pip-audit`, `npm audit` | 0 known vulnerabilities |

## A. Authentication (`backend/tests/test_auth.py`, frontend `app.test.tsx`)

| ID | Test | Expected | Automated by |
|---|---|---|---|
| AUTH-01 | Valid student login | 200, httpOnly cookie, role in `/auth/me` | `test_auth01_valid_login_sets_httponly_cookie` |
| AUTH-02 | Invalid password / unknown email | 401, identical message | `test_auth02_invalid_password_rejected` |
| AUTH-03 | Unauthenticated access | 401 on every protected route | `test_auth03_…`, E2E, route sweep |
| AUTH-04 | Logout | old cookie rejected (server-side revocation) | `test_auth04_logout_invalidates_server_session` |
| AUTH-05 | Student role | student scope only | `test_authorization.py` |
| AUTH-06 | Expired / disabled session | 401 | `test_expired_session_rejected`, `test_disabled_account_cannot_use_session` |
| AUTH-07 | Brute force | 429 after 8 failures | `test_login_throttled_after_repeated_failures` |
| AUTH-08 | CSRF header missing | 403 | `test_state_changing_request_without_csrf_header_rejected` |
| AUTH-09 | UI login lands on role home | dashboard rendered | vitest `signs in and lands on the role's home page` |

## B. Attendance import (`backend/tests/test_upload.py`)

| ID | Test | Expected |
|---|---|---|
| ATT-01 | Valid CSV | imported, analytics refreshed, risk changes reported |
| ATT-02 | Valid XLSX | imported (`attendance_sample.xlsx`; header aliases; blank rows skipped) |
| ATT-03 | Missing column | 422 naming the missing columns |
| ATT-04 | attended > conducted | 422 with row 3 / column / value |
| ATT-05 | Negative value | 422 |
| ATT-06 | Duplicate row in file / existing record | 422 (strict) or update (replace mode) |
| ATT-07 | conducted = 0 | 422, no division error |
| ATT-08 | 10/10 | 100% |
| ATT-09 | Invalid / non-ISO / future dates, non-numeric, decimals, blanks, unknown student/subject, oversized counts, bad characters | 422 per row |
| ATT-10 | One bad row among valid rows | whole file rejected, **zero rows written**, rejected import logged |
| ATT-11 | Wrong file types (.txt, .xls, fake .xlsx, zip-as-csv, empty, header-only) and oversize | 415 / 422 / 413 |
| ATT-12 | Department mismatch, HOD outside scope | 422 |
| ATT-13 | Dry run, opt-in registration of new students/subjects, name-mismatch warning | as specified |

## C. Analytics (`test_engine.py`, `test_analytics_api.py`)

| ID | Test | Expected |
|---|---|---|
| ANA-01 | 5/10 | 50% |
| ANA-02 | 72/100 | 72% |
| ANA-03 | exactly target | 75% boundary: not CRITICAL; inside warning band; target + band → SAFE |
| ANA-04 | projected below target | CRITICAL |
| ANA-05 / 06 | improving / declining trend | IMPROVING / DECREASING (threshold boundary covered) |
| ANA-07 | no history | INSUFFICIENT_DATA; no data → NO_DATA |
| ANA-08 | material decline rule | 100→95 stays SAFE; decline into band → WARNING |
| ANA-09 | explanation present | every result has current, target, trend, projected, risk, reason, action |
| ANA-10 | demo story | after sample upload S003 CRITICAL, recovery verified mathematically |

## D. Recovery

`(A+X)/(C+X) ≥ T`: A=72, C=100, T=0.75 → X=12, plus already above / exactly at target, very low
attendance (10/100 → 260), T=100% unreachable, zero conducted, not recoverable within the
remaining term, and a parametrised minimality check over 60 combinations. The API endpoint
and the UI calculator use the same function.

## E. Authorization

Student cannot read another student (4 endpoints) or use staff endpoints, cannot approve
(including own request). Mentors and HODs are limited to their scope. Exam Cell is read-only.
Alerts are private. Import history is scoped. A route sweep covers every endpoint.

## F. Condonation (`test_condonation.py`, E2E)

Submit → PENDING → mentor sees it and gets an alert → approve/reject (reject needs a comment)
→ student sees status, comment, history and an alert. Duplicates are refused. A terminal state
cannot change (409). Ineligible SAFE students are refused. Withdraw works for the owner only.
Unrelated reviewers are refused.

## G. Deployment / E2E (`e2e/tests/acceptance.spec.ts`)

Health, the full judge flow (23 steps), HOD scoping, 390 px mobile layout without horizontal
scroll, unauthenticated API and unknown routes, and no JS errors or 5xx responses during the flow.
Run against the production Docker image with `APP_ENV=production` and `Secure` cookies.

## H. Navigation, layout and accessibility

| ID | Test | Automated by |
|---|---|---|
| UX-01 | Phone bottom tab bar: 3 tabs for students, each page reachable, no horizontal overflow | E2E `phone layout: bottom navigation…` |
| UX-02 | No WCAG 2.1 AA violations on login, dashboard, students, student detail, upload, reports, student home | E2E `key pages have no WCAG 2.1 AA violations` (axe-core) |
| UX-03 | Desktop top navigation, account menu, sign out | E2E acceptance flow |

## I. Android app

| ID | Test | Automated by |
|---|---|---|
| APP-01 | Server picker rejects non-HTTPS servers and checks `/health` | E2E `native-app.spec.ts`, device smoke test |
| APP-02 | Login issues a bearer token (no cookies), data loads cross-origin | E2E app mode, `test_mobile_login_returns_bearer_token_and_no_cookie` |
| APP-03 | Logout revokes the token | E2E app mode, `test_bearer_token_authenticates_and_logout_revokes_it` |
| APP-04 | CORS admits only the app origins | `test_cors_allows_only_configured_app_origins` |
| APP-05 | Real APK on Android 14: first launch, student and admin flows, tabs, hardware back, layout | `e2e/android/app-smoke.mjs` on the emulator (screenshots uploaded) |

## Release gate

No release if any P0 flow is broken. CI runs all of the above on every push.
