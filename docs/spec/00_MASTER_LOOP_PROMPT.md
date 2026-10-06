# AttendAI — Autonomous Build & Deployment Loop Prompt

You are the lead engineer responsible for turning the existing AttendAI repository into a **deployed, working, evaluation-ready prototype**.

## Mission

Build, test, integrate, and deploy the simplest reliable version of:

> **AttendAI — Attendance Shortage Early Warning & Condonation System**

The final system must let a judge:
1. Open the deployed application.
2. Log in using demo credentials.
3. Upload attendance CSV/XLSX as an authorized user.
4. See the data processed successfully.
5. Select a student.
6. View current and subject-wise attendance.
7. View projected attendance.
8. See an explainable risk classification.
9. See the recovery recommendation.
10. See mentor/admin risk information.
11. Submit and review a condonation request.
12. View department-level shortage/risk reporting.

The source architecture specifies React + FastAPI + PostgreSQL + Pandas, with analytics separated from API routes. Preserve this architecture unless the existing repository already has a stronger equivalent. The uploaded source documents are the source of truth for product scope and architecture.

---

# OPERATING MODE: LOOP UNTIL DONE

Do NOT stop after creating a plan.

Repeat this loop:

```text
INSPECT
  ↓
UNDERSTAND CURRENT STATE
  ↓
IMPLEMENT HIGHEST-VALUE BLOCKER
  ↓
RUN TESTS
  ↓
FIX FAILURES
  ↓
RUN BUILD
  ↓
RUN INTEGRATION CHECKS
  ↓
VERIFY UI FLOW
  ↓
VERIFY DEPLOYMENT
  ↓
RECHECK REQUIREMENTS
  ↓
IF ANY BLOCKER EXISTS → CONTINUE LOOP
  ↓
IF ALL GATES PASS → FINAL AUDIT
```

You may change, refactor, add, remove, or replace implementation details when necessary to produce a working prototype.

Do not preserve broken architecture merely because it already exists.

---

# NON-NEGOTIABLE RULES

## 1. Demo first

A feature is not complete merely because a function/API exists.

A feature is complete only when:

```text
database/backend
      +
API
      +
frontend
      +
real UI interaction
      +
test
```

all work together.

## 2. Do not fake production functionality

Do not create fake success states.

Do not display hard-coded analytics while pretending they came from the database.

Demo seed data is allowed, but it must pass through the same real application flow as uploaded data.

## 3. Prefer deterministic explainable analytics

Do NOT introduce ML merely to make the project sound advanced.

Use deterministic, explainable projection/risk logic first.

Every risk result must expose:
- current attendance
- required threshold
- trend/evidence
- projected attendance
- risk level
- reason
- recovery action

## 4. Protect student data

Enforce role authorization server-side.

At minimum:

```text
STUDENT
  own records only

MENTOR
  assigned/authorized students

HOD/ADMIN
  department/reporting scope

EXAM_CELL
  shortage/eligibility/reporting scope
```

Never rely only on frontend route guards.

## 5. No secrets in source control

Use environment variables.

Never commit:
- database passwords
- JWT secrets
- API keys
- private credentials
- production credentials

## 6. Do not ask for permission for routine engineering decisions

Make reasonable engineering decisions yourself.

Ask only if:
- a required external credential is genuinely unavailable,
- deployment requires an irreversible owner decision,
- the repository contains conflicting requirements that cannot safely be resolved.

Otherwise proceed.

---

# PHASE 0 — REPOSITORY RECONNAISSANCE

Before modifying code:

1. Inspect repository structure.
2. Detect frontend framework.
3. Detect backend framework.
4. Detect database layer.
5. Detect package managers.
6. Detect existing authentication.
7. Detect existing deployment configuration.
8. Detect existing tests.
9. Detect environment variable names.
10. Identify what already works.

Do not rebuild working components unnecessarily.

Create/update:

```text
docs/IMPLEMENTATION_STATUS.md
```

with:

```text
Component | Status | Evidence | Blocker | Next action
```

---

# PHASE 1 — CREATE/RECONCILE THE CONTRACTS

Create or update:

```text
docs/REQUIREMENTS.md
docs/API_CONTRACT.md
docs/DATA_MODEL.md
docs/ANALYTICS_SPEC.md
docs/SECURITY_MODEL.md
docs/QA_TEST_PLAN.md
docs/DEPLOYMENT_RUNBOOK.md
docs/DEMO_SCRIPT.md
```

Do not let these become paperwork detached from implementation.

They are executable engineering contracts.

---

# PHASE 2 — P0 IMPLEMENTATION

Implement in this order:

## P0.1 Authentication

Required:
- login
- role-aware session
- protected routes
- server-side authorization
- logout
- useful error messages

Demo roles:

```text
student
mentor
admin
exam_cell
```

Use secure password hashing.

---

## P0.2 Attendance Import

Accept:
- CSV
- XLSX

Validate:
- file extension
- file size
- required columns
- numeric values
- duplicate records
- invalid student/subject references
- zero/negative conducted classes
- attended > conducted

Return useful row-level errors.

Do not partially corrupt the database.

Prefer transactional import behavior:

```text
validate entire file
      ↓
if invalid → reject with report
      ↓
if valid → persist
```

---

## P0.3 Attendance Calculation

Core formula:

```text
attendance_percentage =
    attended / conducted * 100
```

Use safe handling for:

```text
conducted = 0
```

Never divide by zero.

Support:
- overall attendance
- subject attendance
- department aggregation

---

## P0.4 Projection Engine

Implement deterministic future projection.

Minimum required inputs:

```text
current attended
current conducted
recent trend
future classes assumption
target threshold
```

The projection must be explainable.

Do not claim statistical/ML accuracy.

---

## P0.5 Risk Engine

Minimum levels:

```text
SAFE
WARNING
CRITICAL
```

Thresholds must be configurable.

A sensible default is:

```text
SAFE:
projected attendance >= target

WARNING:
projected attendance is near target / trend indicates deterioration

CRITICAL:
projected attendance < target
```

The exact thresholds must live in configuration, not scattered magic numbers.

Every risk object should include:

```json
{
  "level": "CRITICAL",
  "current_percentage": 72,
  "projected_percentage": 69,
  "target_percentage": 75,
  "reason": "Projected attendance is below the required threshold.",
  "recommended_action": "Attend the next available classes and review recovery requirement."
}
```

---

## P0.6 Student Dashboard

Must show:

- overall attendance
- subject cards/table
- risk level
- projection
- reason
- recovery calculation
- alerts
- condonation status

Loading, empty and error states are mandatory.

---

## P0.7 Mentor Dashboard

Must show:

- assigned students
- current attendance
- projected attendance
- risk level
- risk reason
- trend
- high-risk list
- condonation requests

---

## P0.8 Admin/HOD Dashboard

Must show:

- total students
- safe/warning/critical counts
- department percentage
- shortage list
- subject-level patterns
- report/export capability if practical

---

# PHASE 3 — P1 IMPLEMENTATION

Implement:

1. Recovery calculator
2. Alerts
3. Condonation workflow
4. Department reports

Condonation flow:

```text
Student submits
    ↓
PENDING
    ↓
Mentor/Admin reviews
    ↓
APPROVED / REJECTED
    ↓
Decision recorded
```

Store decision history where practical.

---

# PHASE 4 — SECURITY

Verify:

- password hashing
- authorization on every protected API
- ownership checks
- file validation
- upload size limits
- safe parsing
- SQL injection protection through ORM/parameterized queries
- CORS restricted to deployed frontend
- secure cookie/token handling
- secrets only in environment
- no sensitive records in logs
- no stack traces exposed to users in production

Student A must never retrieve Student B's private records by changing an ID in a request.

---

# PHASE 5 — TESTING LOOP

Run:

```text
unit tests
backend tests
analytics tests
API tests
frontend tests
build
integration tests
```

At minimum test:

### Attendance
- 0/0
- 0/10
- 10/10
- 5/10
- attended > conducted
- negative values
- duplicate records
- missing columns

### Risk
- safely above threshold
- exactly threshold
- below threshold
- deteriorating trend
- improving trend
- no history

### Recovery
Verify:

```text
(A + X)/(C + X) >= T
```

and calculate the minimum integer X where possible.

### Security
- student cannot access another student
- mentor cannot access unauthorized scope
- admin access works
- unauthenticated access rejected

---

# PHASE 6 — UI QUALITY PASS

Before deployment:

- remove console errors
- remove broken links
- fix mobile overflow
- fix loading states
- fix empty states
- fix error states
- ensure readable charts
- ensure risk explanation is visible
- ensure important actions are obvious
- ensure no placeholder text remains
- ensure no "coming soon" exists on required MVP flows

---

# PHASE 7 — DEPLOYMENT

Deploy:

```text
Frontend
Backend
PostgreSQL
```

Configure:
- production environment variables
- CORS
- database migrations
- seed/demo data
- health endpoint
- production build
- API base URL

Add:

```text
GET /health
```

Expected:

```json
{
  "status": "ok"
}
```

Verify the deployed frontend communicates with the deployed backend.

Do not declare success because deployment merely builds.

Perform the complete demo flow against the deployed URL.

---

# PHASE 8 — FINAL ACCEPTANCE TEST

Execute this exact scenario:

```text
1. Open deployed URL
2. Login as admin
3. Upload sample attendance file
4. Verify import result
5. Open dashboard
6. Find a critical student
7. Open student detail
8. Verify attendance calculation
9. Verify projected attendance
10. Verify explanation
11. Verify recovery recommendation
12. Login as mentor
13. Verify student appears in risk list
14. Login as student
15. Verify own dashboard
16. Submit condonation request
17. Login as mentor/admin
18. Review request
19. Approve/reject
20. Verify student sees status
21. Open department report
22. Verify totals
```

If any step fails, fix it and repeat from the failed step.

---

# STOP CONDITION

You are NOT finished when:
- code compiles
- tests pass locally
- frontend deploys
- backend deploys

You are finished only when:

```text
LOCAL BUILD       PASS
UNIT TESTS        PASS
API TESTS         PASS
INTEGRATION       PASS
ROLE SECURITY     PASS
PRODUCTION BUILD  PASS
DEPLOYMENT        PASS
LIVE DEMO FLOW    PASS
REQUIREMENTS      PASS
```

If deployment is impossible because credentials are unavailable, finish all code/configuration possible, produce exact deployment commands, and clearly identify the single external action blocking live deployment.

---

# FINAL REPORT

Create:

```text
docs/FINAL_STATUS.md
```

with:

```text
Project:
Deployment URL:
Backend URL:
Health URL:

Implemented:
- ...

Tests:
- ...

Known limitations:
- ...

Demo accounts:
- ...

Environment variables:
- ...

Deployment blocker:
- None / exact blocker

Acceptance flow:
1. PASS
2. PASS
...
```

Never claim a deployed URL is working unless you actually verified it.
