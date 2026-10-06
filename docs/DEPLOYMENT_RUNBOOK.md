# AttendAI — Deployment Runbook

## Topology

```
User ──HTTPS──► Render web service "attendai" (Docker: FastAPI + built React SPA, same origin)
                         │  private network
                         ▼
                Render PostgreSQL "attendai-db"
```

Serving the SPA from the API keeps the session cookie first-party, so there are no
third-party-cookie or CORS problems. A split deployment is supported too (see the end of this runbook).

## Environment variables

| Variable | Required | Production value / notes |
|---|---|---|
| `DATABASE_URL` | yes | `postgres://…` or `postgresql://…` accepted (normalised to psycopg 3). Render: from the database |
| `SECRET_KEY` | yes in production | ≥ 32 random chars. Render: `generateValue: true`. Startup fails without it |
| `APP_ENV` | yes | `production` (Secure cookies, HSTS, API docs off) |
| `WEB_CONCURRENCY` | no | uvicorn workers, default 1 (free tier memory) |
| `SEED_DEMO_DATA` | no | `true` seeds fictional demo data once (idempotent) |
| `DEMO_MODE` | no | `true` shows the demo-account panel on the login page |
| `DEMO_PASSWORD` | no | default `Demo@2026` |
| `CORS_ORIGINS` / `FRONTEND_ORIGIN` | only for split deployments | explicit origins, never `*` |
| `MOBILE_APP_ORIGINS` | no | Android/iOS app WebView origins (default `https://localhost,capacitor://localhost`; `""` disables the app) |
| `COOKIE_SECURE`, `COOKIE_SAMESITE` | no | default Secure in production, `lax` |
| `TARGET_PERCENTAGE`, `WARNING_BAND_POINTS`, `TREND_RECENT_PERIODS`, `TREND_THRESHOLD_POINTS`, `DEFAULT_PLANNED_CLASSES` | no | analytics policy (75, 5, 2, 5, 60) |
| `MAX_UPLOAD_MB`, `MAX_UPLOAD_ROWS` | no | 5, 20000 |
| `FORWARDED_ALLOW_IPS` | no | proxy IPs trusted for `X-Forwarded-For` (default `*`) |
| `VITE_API_BASE_URL` | build arg, split deployments only | default `/api` |

## Deploy on Render (recommended, about 5 minutes)

1. Sign in at <https://dashboard.render.com> with the GitHub account that owns
   `chsrvyt/hackathon-ieee` (or grant Render access to the repository).
2. **New → Blueprint**, select the repository and the branch to deploy, then **Apply**.
   `render.yaml` creates:
   * PostgreSQL `attendai-db` (free plan, no public access)
   * Web service `attendai` (Docker, health check `/health`, `SECRET_KEY` generated)
3. The first deploy builds the image, runs `alembic upgrade head`, seeds the demo data and starts
   uvicorn. Watch the logs for `Seeded demo data` and `Application startup complete`.
4. Run the smoke test below against `https://<service>.onrender.com`.

Free-plan notes: the web service sleeps after 15 minutes idle (first request takes about 30–60 s),
and free PostgreSQL databases expire after 30 days. Upgrade the plans for anything beyond a demo.

### Same thing with the Render API (if an API key is available)

```bash
export RENDER_API_KEY=…   # from the Render dashboard → Account settings → API keys
# Blueprints are applied from the dashboard; the API can then trigger deploys:
curl -s -H "Authorization: Bearer $RENDER_API_KEY" https://api.render.com/v1/services?name=attendai
curl -s -X POST -H "Authorization: Bearer $RENDER_API_KEY" https://api.render.com/v1/services/<service-id>/deploys
```

## Any other Docker host

```bash
docker build -t attendai .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB \
  -e SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  -e APP_ENV=production -e SEED_DEMO_DATA=true -e DEMO_MODE=true \
  attendai
```

Local production-like stack: `docker compose up --build` → <http://localhost:8000>.
Behind a TLS-inspecting proxy, pass its CA as a build secret:
`docker build --secret id=ca_bundle,src=/path/to/ca.pem -t attendai .`

## Android app

After the website is live, set the repository variable **`ATTENDAI_SERVER_URL`** (Settings → Secrets
and variables → Actions → Variables) to the site URL. Then run **Actions → Android app → Run workflow**,
so the APK opens with the server pre-filled. Without it, users type the address on first launch.
See [MOBILE_APP.md](MOBILE_APP.md).

## Database

* Migrations run automatically on every container start (`backend/start.sh`). They can also be
  run manually with `alembic upgrade head`.
* Seeding is idempotent (skipped when `admin@attendai.demo` exists). To reset a *demo*
  database: `python -m app.seed --reset` (this wipes **all** application data).
* After changing analytics policy variables, call `POST /api/analytics/recompute` as admin.

## Smoke test (after every deploy)

```bash
BASE=https://<service>.onrender.com
curl -s $BASE/health                                   # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" $BASE/        # 200 (SPA)
curl -s -o /dev/null -w "%{http_code}\n" $BASE/api/analytics/overview   # 401 (auth enforced)
# full browser acceptance flow (≈10 s):
cd e2e && npm ci && npx playwright install chromium && E2E_BASE_URL=$BASE npx playwright test
```

Manual: sign in as admin → upload `sample_data/attendance_sample.csv` (tick "Replace existing
records" on re-runs) → dashboard → Rohan Verma CRITICAL with explanation and recovery → mentor
→ student submits condonation → mentor approves → student sees APPROVED → Exam Cell report and
CSV export.

## Rollback

1. Render → service → **Events** → previous successful deploy → **Rollback** (or redeploy the
   last good commit).
2. The schema has a single migration, so there are no down-migrations to run for app rollbacks.
   For future migrations, roll back the app first, then `alembic downgrade -1` only if the
   schema change is incompatible.
3. Record the failure, fix locally (tests + E2E against `docker compose`), redeploy, and repeat the
   smoke test.

## Split frontend/backend deployment (optional)

Build the frontend with `VITE_API_BASE_URL=https://api.example.edu/api` and host `frontend/dist`
on any static host (with an SPA fallback to `index.html`). On the API set
`CORS_ORIGINS=https://app.example.edu`, `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true`.
Browsers that block third-party cookies will break this mode unless both are on the same site
(e.g. `app.example.edu` / `api.example.edu`). That is why the single-origin setup is the default.
