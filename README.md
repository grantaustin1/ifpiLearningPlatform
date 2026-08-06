# IFPI Learning Platform

Multi-tenant LMS for the International Fitness Professionals Institute — course
authoring (AI-assisted), marketplace catalog, exams, certificates, live sessions,
billing (Stripe), ERP360 SSO bridge, and per-academy branding.

**Stack**: FastAPI + SQLAlchemy (SQLite dev / PostgreSQL prod) · React 18 + TypeScript (CRA) · supervisor-managed services.

## Quickstart

```bash
# Backend deps
cd backend && pip install -r requirements.txt

# Frontend deps (yarn only — npm breaks the lockfile)
cd frontend && yarn install

# Create the two .env files below, then:
sudo supervisorctl restart backend frontend
```

Backend listens on `0.0.0.0:8001`, frontend dev server on `:3000`.
All API routes are prefixed with `/api`.

## Environment setup

`.env` files are **gitignored** — a fresh clone will not start until you create them.

### `backend/.env` (required)

| Key | Example / dev value | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./ifpi_lms.db` | SQLAlchemy URL. Use PostgreSQL in production. |
| `JWT_SECRET` | any long random string | Signs access/refresh tokens and ICS subscribe tokens. Rotate for prod. |
| `ENVIRONMENT` | `development` | `production` tightens cookie + error behaviour. |
| `ALLOWED_ORIGINS` | `*` | CORS allow-list (comma-separated). `CORS_ORIGINS` deploy secret overrides it. |
| `STORAGE_BACKEND` | `local` | `local` \| `s3` \| `gcs` (S3/GCS need bucket + cloud creds). |
| `STORAGE_PATH` | `./uploads` | Upload dir for the `local` backend (course covers, media). |
| `CSRF_ENABLED` | `true` | Double-submit CSRF cookie enforcement for cookie-auth mutations. |
| `AUTH_COOKIE_MODE` | `dual` | `off` \| `dual` \| `on` — cookie vs bearer auth mode. |
| `SMTP_ENCRYPTION_KEY` | 32-byte url-safe base64 (`python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`) | Encrypts per-tenant SMTP passwords and TOTP secrets. **Required** for SMTP settings + 2FA. |
| `EMERGENT_LLM_KEY` | `sk-emergent-…` | AI builder / tutor / embeddings (OpenAI-compatible via Emergent proxy). |
| `STRIPE_API_KEY` | `sk_test_…` | Paid-course checkout. Endpoints return 503 without it. |
| `SSO_ENABLED` | `true` | Enables the ERP360 SSO exchange endpoint. |
| `ERP360_SSO_SHARED_SECRET` | shared HS256 secret | Verifies ERP360-minted SSO JWTs (same value on both sides). |
| `IFPI_WEBHOOK_OUTBOUND_SECRET` | any random string | Signs outbound ERP360 webhooks / inbound sync verification. |
| `ALLOW_TEST_TOKEN_HEADER` | `true` (dev/test **only**) | Enables `X-Return-Token` + `X-Test-Client-Ip` test bypasses used by the pytest suite. **Must be absent/false in production.** |

Optional: `TAVILY_API_KEY` (deep research), `REDIS_URL` (shared rate limiting),
`PUBLIC_BASE_URL` (links in emails/cert verify), `SENTRY_DSN`, `DB_POOL_SIZE` etc.
See `backend/core/config.py` for the full list and defaults.

### `frontend/.env` (required)

| Key | Example | Purpose |
|---|---|---|
| `REACT_APP_BACKEND_URL` | `https://your-host.example.com` | Base URL the SPA calls (`{url}/api/...`). No trailing slash. |
| `WDS_SOCKET_PORT` | `443` | Hot-reload websocket port behind an HTTPS ingress. |

## Test accounts (dev DB)

See `memory/test_credentials.md`. Defaults: admin `admin@ifpi.org` / `admin123`
(forced password change on first login), learner `learner@ifpi.org` / `learner123`.

## Running the test suite

Integration tests hit the running backend over HTTP:

```bash
cd backend
export REACT_APP_BACKEND_URL=<your preview URL>          # or set in frontend/.env
export IFPI_WEBHOOK_OUTBOUND_SECRET=<same as backend/.env>
export ERP360_SSO_SHARED_SECRET=<same as backend/.env>
python -m pytest tests/ -q
```

## Docs

- `docs/IFPI_SETUP_MANUAL.md` — first-time setup walkthrough
- `docs/IFPI_USER_MANUAL.md` — full route/model index (auto-generated blocks)
- `memory/DEPLOY_RUNBOOK.md` — production deployment checklist
