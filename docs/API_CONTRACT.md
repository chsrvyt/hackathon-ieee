# AttendAI — API Contract (as implemented)

Base path: `/api`. Health is also served at `/health`. Interactive OpenAPI docs are at
`/api/docs` outside production (disabled when `APP_ENV=production`).

## Conventions

* **Auth (web)**: `POST /api/auth/login` sets an httpOnly session cookie (`attendai_session`).
  The browser sends it automatically (`credentials: "include"`).
* **Auth (Android app)**: the same login with header `X-AttendAI-Client: mobile` returns
  `{"user", "token", "expires_at"}` and sets no cookie. The app then sends
  `Authorization: Bearer <token>`. Tokens are server-side sessions: they expire and are revoked by
  `POST /auth/logout`. CORS admits only the app origins in `MOBILE_APP_ORIGINS`.
* **CSRF guard**: every `POST/PUT/PATCH/DELETE` under `/api/` must send
  `X-Requested-With: AttendAI`, or it gets `403 CSRF_CHECK_FAILED`.
* **Errors** always use this shape, with no stack traces:

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Attendance cannot exceed conducted classes.", "details": [] } }
```

| HTTP | Codes |
|---|---|
| 401 | `UNAUTHENTICATED`, `SESSION_EXPIRED`, `INVALID_CREDENTIALS` |
| 403 | `FORBIDDEN`, `CSRF_CHECK_FAILED` |
| 404 | `NOT_FOUND` |
| 409 | `DUPLICATE_PENDING`, `INVALID_TRANSITION`, `CONFLICT` |
| 413 / 415 | upload too large / unsupported or corrupt file |
| 422 | `VALIDATION_ERROR`, `NOT_ELIGIBLE` |
| 429 | `RATE_LIMITED` (login throttling) |
| 500 | `INTERNAL_ERROR` (generic message + request id) |

Role scopes are defined in [SECURITY_MODEL.md](SECURITY_MODEL.md). "Scoped" means the
endpoint only returns students the caller is authorised for, and 403 for a specific
out-of-scope id.

## Health

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/health` (also `/api/health`) | none | `200 {"status":"ok"}`; `503 {"status":"error","database":"unavailable"}` if the DB is unreachable |

## Authentication

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/login` | none | body `{"email","password"}` → `{"user": User}` + cookie (web), or `{"user","token","expires_at"}` with `X-AttendAI-Client: mobile`. 8 failures / 15 min per IP+email → 429 |
| POST | `/auth/logout` | cookie or bearer | revokes the server-side session, clears the cookie |
| GET | `/auth/me` | required | `{"user": User}`; 401 when signed out |
| GET | `/auth/session` | optional | `{"user": User \| null}` (startup probe, never 401) |
| GET | `/auth/demo-accounts` | none | `{"enabled", "password", "accounts"}` only when `DEMO_MODE=true` |

`User = {id, name, email, role: STUDENT|MENTOR|ADMIN|EXAM_CELL, department|null, student_id|null}`

## Students

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/students` | MENTOR, ADMIN, EXAM_CELL (scoped) | query: `search`, `risk` (comma list), `department_id`, `sort` (`risk`,`name`,`roll`,`current`,`projected`), `page`, `page_size≤100` → `{items, total, page, page_size}` |
| GET | `/students/{id}` | all (scoped; a student only themself) | profile + latest analytics snapshot |

## Attendance

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/attendance/upload` | ADMIN (HOD: own department rows only) | multipart: `file` (.csv/.xlsx ≤ `MAX_UPLOAD_MB`), `mode=strict\|replace`, `register_new=bool`, `dry_run=bool` |
| GET | `/attendance/template.csv` | any signed-in | CSV template |
| GET | `/attendance/imports` | ADMIN | last 20 imports (HOD: own uploads only) |
| GET | `/attendance/student/{student_id}` | scoped | raw period records |
| GET | `/attendance/subject/{subject_id}` | staff (scoped) | per-student totals for a subject |

Upload response (200 on success; 422/413/415 with the same body plus `error` on rejection):

```json
{
  "success": true, "dry_run": false, "import_id": 2, "filename": "attendance_sample.csv", "file_type": "csv",
  "mode": "strict", "rows_total": 24, "rows_processed": 24, "rows_rejected": 0,
  "rows_inserted": 24, "rows_updated": 0, "students_affected": 8, "subjects_affected": 3,
  "created_students": [], "created_subjects": [], "date_range": ["2026-09-01", "2026-09-01"],
  "errors_total": 0, "errors": [], "warnings": [],
  "risk_changes": [{"student_id": 3, "roll_number": "S003", "name": "Rohan Verma", "previous": "WARNING", "current": "CRITICAL"}]
}
```

Each error/warning: `{"row": 3, "column": "classes_attended", "value": "12", "message": "..."}`.
When `success` is false, nothing was written (`rows_processed: 0`).

## Analytics and reports

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/analytics/student/{id}` | scoped | full live analysis, see below |
| GET | `/analytics/risk-students` | staff (scoped) | `level=CRITICAL,WARNING`, `limit≤200` |
| GET | `/analytics/overview` | staff (scoped) | totals, risk distribution, histogram, departments, subject patterns, top at-risk, pending condonations, recent imports (admin) |
| GET | `/analytics/department/{id}` | ADMIN (own dept for HOD), EXAM_CELL | summary + `shortage_students` (below target overall or in any subject, with latest condonation status) |
| GET | `/reports/department/{id}/export.csv` | as above | CSV shortage list (formula-injection safe) |
| GET | `/analytics/recovery` | any signed-in | `attended, conducted, target (0-100], remaining` → recovery plan |
| POST | `/analytics/recompute` | ADMIN (scoped) | refresh projection snapshots |

`GET /analytics/student/{id}` (abridged):

```json
{
  "student_id": 3,
  "student": {"roll_number": "S003", "name": "Rohan Verma", "department": {...}, "mentor": {...}},
  "current_percentage": 74.48, "projected_percentage": 72.84, "target_percentage": 75.0,
  "risk_level": "CRITICAL", "trend": "DECREASING",
  "reason": "Projected attendance of 72.8% is below the 75% target, assuming ...",
  "recommended_action": "Attend the next 3 classes without an absence to return to 75%, ...",
  "recovery": {"status": "RECOVERABLE", "possible": true, "classes_required": 3, "remaining_classes": 87,
               "classes_needed_of_remaining": 66, "max_achievable_percentage": 84.05, "buffer_classes": 0, "message": "..."},
  "overall": {"classes_attended": 108, "classes_conducted": 145, "trend_detail": {...}, "projection": {...}, "risk_rules": [...]},
  "subjects": [{"subject": {"code": "CS103", ...}, "current_percentage": 72.0, "risk_level": "CRITICAL", ...}],
  "timeline": [{"date": "2026-09-01", "conducted": 58, "attended": 39, "period_percentage": 67.24, "cumulative_percentage": 74.48}],
  "policy": {"target_percentage": 75, "warning_band_points": 5, "trend_recent_periods": 2, "trend_threshold_points": 5},
  "disclaimer": "Decision-support estimate ..."
}
```

## Alerts

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/alerts` | own | `unread_only`, `limit` → `{items, unread_count}` |
| PATCH | `/alerts/{id}/read` | own | 404 for alerts of other users (no probing) |
| POST | `/alerts/read-all` | own | |

## Condonation

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/condonation` | STUDENT | `{"reason": 20–2000 chars, "subject_id": optional}` → 201. Only when the student (or that subject) is WARNING/CRITICAL (`NOT_ELIGIBLE` otherwise). One pending request per subject/overall (`DUPLICATE_PENDING`) |
| GET | `/condonation/student/{student_id}` | scoped | newest first, with `history` |
| GET | `/condonation/pending` | staff (scoped) | |
| GET | `/condonation?status=` | staff (scoped) | `PENDING`,`APPROVED`,`REJECTED`,`WITHDRAWN`,`ALL`; `can_review` flag |
| PATCH | `/condonation/{id}/decision` | assigned MENTOR, ADMIN in scope | `{"decision": "APPROVED"\|"REJECTED", "comment"}`; comment required to reject; only from PENDING (`INVALID_TRANSITION`) |
| PATCH | `/condonation/{id}/withdraw` | owning STUDENT | PENDING → WITHDRAWN |

## Reference data

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/departments` | signed-in (scoped) | |
| GET | `/subjects` | signed-in | `department_id` filter |
