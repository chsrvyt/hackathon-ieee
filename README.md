# AttendAI — Attendance Shortage Early Warning & Condonation System

> Don't just show attendance. Predict the shortage early and recommend the next action.

AttendAI imports institutional attendance (CSV/XLSX), works out where every student will
finish the term if their recent pattern continues, classifies the risk as
**SAFE / WARNING / CRITICAL** with a plain-language reason, tells the student exactly how
many classes they must attend to recover, and runs the condonation (attendance-shortage
exemption) workflow between students, mentors, HODs and the Exam Cell.

The analytics are **deterministic and explainable**. No machine learning is used or claimed.

## What it does

| Role | Capabilities |
|---|---|
| **Student** | Own overall and subject-wise attendance, projected end-of-term %, risk level and reason, recovery plan and what-if calculator, attendance timeline, alerts, submit/withdraw condonation requests and see decisions |
| **Mentor** | Assigned students only: risk distribution, students needing attention, trends, alerts on risk changes, approve/reject condonation requests |
| **Admin / HOD** | Upload CSV/XLSX attendance, institution-wide dashboard (or one department for an HOD), student drill-down, department reports with CSV export, condonation review, import history |
| **Exam Cell** | Read-only shortage/eligibility reporting across departments, condonation decision visibility |

Authorization is enforced **on the server** for every endpoint. The UI only hides links.

## Architecture

```
Browser ──► FastAPI (serves the React SPA + /api) ──► PostgreSQL
              │
              ├─ app/services/importer.py      Pandas CSV/XLSX validation → transactional import
              ├─ app/analytics/engine.py       pure, exact-arithmetic risk / projection / recovery
              ├─ app/analytics/service.py      DB glue, projection snapshots, risk-change alerts
              └─ app/routers/*                 thin HTTP layer + role scopes (app/authz.py)
```

* **Backend**: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, Pandas + openpyxl
* **Frontend**: React 19 + TypeScript, Vite, React Router, TanStack Query, hand-drawn SVG charts
* **Database**: PostgreSQL 16 (constraints for integrity, partial unique indexes)
* **Mobile**: Android app (Capacitor 8) built by GitHub Actions, emulator-tested, and published as a GitHub Release
* **Deployment**: one Docker image (API + built SPA, same origin) + managed PostgreSQL (Render Blueprint)

## Navigation and mobile

* **Desktop**: sticky top navigation bar (sections with icons and counts, account menu, sign out).
* **Phones**: compact app bar plus a bottom tab bar (Home/Dashboard, Students, Upload, Requests,
  Reports, Alerts by role). Tables become cards, touch targets are 44 px, and safe areas are respected.
* **Android app**: download the APK from the repository's **Releases** page (`android-latest`). On
  first launch enter the website address, then sign in. Details: [docs/MOBILE_APP.md](docs/MOBILE_APP.md).

## Quick start (Docker, recommended)

```bash
docker compose up --build
# open http://localhost:8000
```

This starts PostgreSQL, runs migrations, seeds fictional demo data and serves the app.

## Demo accounts

All demo accounts share the password **`Demo@2026`**. The data is fictional.

| Account | Role / scope |
|---|---|
| `admin@attendai.demo` | Admin, all departments |
| `hod.ece@attendai.demo` | Admin, ECE department only (HOD) |
| `mentor@attendai.demo` | Mentor of the 8 CSE students |
| `mentor.ece@attendai.demo` | Mentor of the 6 ECE students |
| `examcell@attendai.demo` | Exam Cell (read-only reporting) |
| `student@attendai.demo` | Student Rohan Verma (S003, CSE) |
| `s001@…`, `s002@…`, `e001@…`, … `@attendai.demo` | other students |

The login page lists these accounts as one-click buttons when `DEMO_MODE=true`.

**Demo story:** the seed loads CSE attendance up to 17 Aug. Sign in as admin and upload
[`sample_data/attendance_sample.csv`](sample_data/attendance_sample.csv) (the 1 Sep period).
Rohan Verma moves WARNING → CRITICAL, Vihaan Shah WARNING → CRITICAL, Aarav Sharma
SAFE → WARNING, and Meera Joshi *improves* CRITICAL → WARNING. Alerts go to the
students and their mentor. See [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).
[`sample_data/attendance_invalid_example.csv`](sample_data/attendance_invalid_example.csv)
shows the row-level validation report.

## Local development

```bash
# PostgreSQL running locally with a database "attendai" (user/password attendai)
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql://attendai:attendai@localhost:5432/attendai DEMO_MODE=true
alembic upgrade head
python -m app.seed            # --reset wipes and reseeds
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm ci
npm run dev                   # http://localhost:5173 (proxies /api to :8000)
```

## Tests

```bash
cd backend  && pytest                       # 181 tests, needs PostgreSQL database "attendai_test"
cd frontend && npx tsc -b && npx vitest run # 11 tests
cd e2e      && npm ci && E2E_BASE_URL=http://localhost:8000 npx playwright test   # acceptance, phone layout, WCAG 2.1 AA
# app-mode test: also serve frontend/dist on another origin and set E2E_NATIVE_URL (see docs/MOBILE_APP.md)
```

CI (`.github/workflows/ci.yml`) runs backend lint and tests on PostgreSQL, frontend
typecheck, tests and build, the Playwright suite (including app mode and accessibility) and a
Docker build. `.github/workflows/android.yml` builds the APK, tests it on an Android emulator and
publishes it.

## Deployment

See [docs/DEPLOYMENT_RUNBOOK.md](docs/DEPLOYMENT_RUNBOOK.md). The short version on Render is
**New → Blueprint →** select this repository **→ Apply**. `render.yaml` provisions
PostgreSQL and the web service and generates `SECRET_KEY`.

## Documentation

| Document | Contents |
|---|---|
| [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) | Evidence-based status of every component |
| [docs/FINAL_STATUS.md](docs/FINAL_STATUS.md) | Acceptance gates, verification results, blockers |
| [docs/API_CONTRACT.md](docs/API_CONTRACT.md) | Every endpoint, roles, request/response shapes |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | Tables, constraints, indexes |
| [docs/ANALYTICS_SPEC.md](docs/ANALYTICS_SPEC.md) | Exact formulas, windows, thresholds, limitations |
| [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) | Auth, authorization matrix, upload safety, headers |
| [docs/QA_TEST_PLAN.md](docs/QA_TEST_PLAN.md) | Test IDs mapped to automated tests |
| [docs/DEPLOYMENT_RUNBOOK.md](docs/DEPLOYMENT_RUNBOOK.md) | Environment variables, deploy, smoke test, rollback |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | Judge walkthrough |
| [docs/MOBILE_APP.md](docs/MOBILE_APP.md) | Android app: install, security, build pipeline, signing |
| [docs/spec/](docs/spec/) | The original specification pack |
