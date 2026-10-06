# AttendAI — Deployment Runbook

## Target

Deploy a working public prototype with:

```text
Frontend → Backend → PostgreSQL
```

## 1. Production variables

Example:

```env
DATABASE_URL=
SECRET_KEY=
FRONTEND_ORIGIN=
CORS_ORIGINS=
```

Frontend:

```env
VITE_API_BASE_URL=
```

Use names matching the actual repository implementation.

## 2. Database

1. Create production PostgreSQL database.
2. Run migrations.
3. Create seed/demo data.
4. Verify connection.
5. Verify indexes/constraints.

## 3. Backend

Required production behavior:

```text
DEBUG=false
```

Expose:

```http
GET /health
```

Verify:
- startup
- database connection
- migrations
- CORS
- auth
- upload
- analytics

## 4. Frontend

Build production bundle.

Verify:
- API base URL
- authentication
- protected routes
- charts
- forms
- error states

## 5. CORS

Allow only the deployed frontend origin.

Do not use:

```text
*
```

for authenticated production traffic unless there is a documented reason.

## 6. Seed Demo Accounts

Create demo accounts for:

```text
Student
Mentor
Admin
Exam Cell
```

Do not use real personal passwords.

## 7. Smoke Test

After deployment:

```text
GET /health
login
upload
dashboard
analytics
condonation
report
```

## 8. Rollback

If production is broken:

1. Identify last known good deployment.
2. Roll back frontend/backend.
3. Preserve database integrity.
4. Record failure.
5. Fix locally.
6. redeploy.
7. repeat smoke test.

## 9. Important

A successful hosting build is NOT a successful deployment.

The application must pass the complete live demo flow.
