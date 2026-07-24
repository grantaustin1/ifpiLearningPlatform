# IFPI Learning — Production Deployment Guide

This document is the **single source of truth** for taking IFPI Learning from
preview → production on Emergent (or any container platform). Follow the
sections top-to-bottom; skipping a step is very likely to break something.

> **Confirmed by Emergent Support (Feb 2026):** IFPI runs on **external
> PostgreSQL** via the `DATABASE_URL` env var. Do **NOT** convert to
> MongoDB — every model uses SQLAlchemy and 36 Alembic migrations track
> the schema. See `docs/IFPI_INTEGRATION_MATRIX.md` for the ERP360 architectural
> contract this alignment upholds.

---

## 0. Pre-flight

Before you deploy, you need three external accounts provisioned:

| Service | Role | Recommended provider | Free tier? |
| ------- | ---- | -------------------- | ---------- |
| **Postgres** | Primary database | [Neon](https://neon.tech) (serverless) | ✅ 0.5 GB |
| **S3-compatible object store** | User uploads, cert PDFs, SCORM packages | AWS S3 · [Cloudflare R2](https://developers.cloudflare.com/r2/) · [Backblaze B2](https://www.backblaze.com/b2/) | ✅ (R2/B2) |
| **SMTP relay** | Transactional email | [Resend](https://resend.com) · SendGrid · AWS SES · Mailgun | ✅ (Resend 3k/mo) |

Each is required. See §2 for the specific env vars they populate.

---

## 1. Rotate secrets

The default `.env` ships with `dev-only-*` secrets. Rotate before prod:

```bash
# 64-char JWT secret
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Fernet SMTP-encryption key (must be exactly 44 chars base64)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save the outputs — you'll paste them into the deployment env in §3.

---

## 2. Required production env vars

Set every variable in the table below. Anything marked ⚠️ is a **deploy
blocker** — the precheck script (§5) will refuse to boot without it.

### Auth & security

| Var | Required | Example / notes |
| --- | :---: | --- |
| `ENVIRONMENT` | ⚠️ | `production` — enables prod-only middleware |
| `JWT_SECRET` | ⚠️ | 48+ char random from `secrets.token_urlsafe(48)` |
| `JWT_ALGORITHM` |  | `HS256` (default) |
| `JWT_EXPIRATION_MINUTES` |  | `60` (default) |
| `REFRESH_TOKEN_DAYS` |  | `30` (default) |
| `AUTH_COOKIE_MODE` | ⚠️ | `on` |
| `AUTH_COOKIE_SECURE` | ⚠️ | `true` — HTTPS only |
| `AUTH_COOKIE_SAMESITE` |  | `lax` (default). Use `none` if hosting frontend on a different eTLD |
| `CSRF_ENABLED` |  | `true` (default) |
| `ALLOW_TEST_TOKEN_HEADER` | ⚠️ | `false` — must be false in prod |
| `ALLOWED_ORIGINS` | ⚠️ | Comma-separated list, e.g. `https://learn.ifpi.org,https://ifpi.org` |
| `SMTP_ENCRYPTION_KEY` | ⚠️ | Fernet key from §1 |

### Database

| Var | Required | Example |
| --- | :---: | --- |
| `DATABASE_URL` | ⚠️ | `postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/ifpi?sslmode=require` |
| `DB_POOL_SIZE` |  | `20` (per worker) |
| `DB_MAX_OVERFLOW` |  | `10` |
| `DB_POOL_RECYCLE_SECS` |  | `1800` |

### Object storage (uploads, cert PDFs, SCORM ZIPs)

| Var | Required | Example |
| --- | :---: | --- |
| `STORAGE_BACKEND` | ⚠️ | `s3` (or `gcs`) |
| `S3_BUCKET` | ⚠️ | `ifpi-prod-uploads` |
| `S3_REGION` |  | `us-east-2` |
| `S3_ENDPOINT_URL` |  | Set for R2 / B2 / other S3-compatibles. Empty for AWS S3. |
| `AWS_ACCESS_KEY_ID` | ⚠️ | IAM user with `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on the bucket |
| `AWS_SECRET_ACCESS_KEY` | ⚠️ | ↑ |

### Email (transactional)

Pick one transport. Order of preference in `services/outbox_worker._dispatch_one`:
per-tenant SMTP → **system SMTP relay** → ERP360 bridge → stub.

| Var | Required | Example |
| --- | :---: | --- |
| `SYSTEM_SMTP_HOST` | ⚠️ (unless per-tenant SMTP set) | `smtp.sendgrid.net` · `smtp.resend.com` · `email-smtp.us-east-2.amazonaws.com` |
| `SYSTEM_SMTP_PORT` | ⚠️ | `587` (STARTTLS) or `465` (implicit TLS) |
| `SYSTEM_SMTP_USERNAME` | ⚠️ | `apikey` (SendGrid) or SES SMTP user |
| `SYSTEM_SMTP_PASSWORD` | ⚠️ | The API key / password |
| `SYSTEM_SMTP_FROM_EMAIL` | ⚠️ | `no-reply@learn.ifpi.org` — must be a verified sender |
| `SYSTEM_SMTP_FROM_NAME` |  | `IFPI Learning` |

### Redis (rate limiting + scheduler jobstore)

| Var | Required | Example |
| --- | :---: | --- |
| `REDIS_URL` |  | `rediss://default:pass@fly-something.upstash.io:6379/0` — falls back to in-memory (per-pod) if unset |

### Public URLs

| Var | Required | Example |
| --- | :---: | --- |
| `PUBLIC_BASE_URL` | ⚠️ | `https://learn.ifpi.org` — used in email links + cert verify URLs + OG social previews |

### Feature flags (optional)

| Var | Default | Notes |
| --- | --- | --- |
| `SSO_ENABLED` | `false` | Set to `true` only when deploying as an ERP360 sibling |
| `ERP360_SSO_SHARED_SECRET` |  | Only when `SSO_ENABLED=true` |
| `COMPLIANCE_OFFICER_EMAIL` |  | Iter 31 auto-report recipient. Empty = worker is a no-op |
| `COMPLIANCE_REPORT_CADENCE` | `weekly` | `daily` \| `weekly` \| `monthly` |
| `TAVILY_API_KEY` |  | Deep-research feature. Feature disabled if unset |
| `EMERGENT_LLM_KEY` | ⚠️ | AI Authoring Suite. Get one from your Emergent profile → Universal Key |
| `AI_BUILDER_MODEL` | `gpt-4o-mini` |  |
| `AI_BUILDER_PROVIDER` | `openai` |  |

### Frontend env

| Var | Required | Example |
| --- | :---: | --- |
| `REACT_APP_BACKEND_URL` | ⚠️ | `https://api.learn.ifpi.org` — the backend's public URL. **NEVER** point to `localhost` |

---

## 3. Deploy sequence

### 3.1 Provision Postgres (Neon walkthrough)

1. Sign in at [neon.tech](https://neon.tech) → **Create Project**.
2. Region: pick the one closest to your backend region.
3. Copy the **connection string** (starts with `postgresql://`). Neon
   gives you both pooled and direct URLs — use the **pooled** one
   (`-pooler` in the hostname).
4. Paste it into your prod env as `DATABASE_URL`.
5. **Do not** run `alembic upgrade head` yet — the app will do it at boot
   via `scripts/deploy_precheck.py` (see §5).

### 3.2 Provision S3 (R2 walkthrough — cheaper than AWS)

1. Cloudflare dashboard → **R2** → Create bucket `ifpi-prod-uploads`.
2. Settings → Public access → **Allow public read** (needed for cert
   PDFs, branding assets, thumbnails).
3. Manage R2 API tokens → Create token → Object Read/Write. Copy the
   Access Key + Secret.
4. Env vars:
   ```
   STORAGE_BACKEND=s3
   S3_BUCKET=ifpi-prod-uploads
   S3_ENDPOINT_URL=https://<your-account>.r2.cloudflarestorage.com
   AWS_ACCESS_KEY_ID=<from step 3>
   AWS_SECRET_ACCESS_KEY=<from step 3>
   ```

### 3.3 Provision SMTP (Resend walkthrough)

1. [resend.com](https://resend.com) → sign in → Domains → Add.
2. Add the DNS records they show (SPF, DKIM, DMARC — normally 3 records).
3. Wait for verification (≤5 min).
4. API Keys → Create → paste as `SYSTEM_SMTP_PASSWORD`. Username is
   literally the word `resend`.
5. Env vars:
   ```
   SYSTEM_SMTP_HOST=smtp.resend.com
   SYSTEM_SMTP_PORT=587
   SYSTEM_SMTP_USERNAME=resend
   SYSTEM_SMTP_PASSWORD=<the api key>
   SYSTEM_SMTP_FROM_EMAIL=no-reply@your-verified-domain
   SYSTEM_SMTP_FROM_NAME=IFPI Learning
   ```

### 3.4 Emergent deployment

1. In Emergent, open your app → **Deploy** tab.
2. Add every ⚠️ env var from §2 to the deployment env.
3. Click **Deploy**. The container will:
   - Run `alembic upgrade head` (via `deploy_precheck.py`)
   - Boot the FastAPI backend on `:8001`
   - Boot the React frontend on `:3000`

### 3.5 Post-deploy smoke tests

Once the deployment settles, run:

```bash
# Health
curl -f https://api.learn.ifpi.org/api/health

# Public catalog (no auth)
curl -f https://api.learn.ifpi.org/api/marketplace/courses

# Login (should set an HttpOnly Set-Cookie)
curl -i -X POST https://api.learn.ifpi.org/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@ifpi.org","password":"admin123"}'
```

All three must return `200`. If login returns `401`, the seed migration
didn't run — connect to Postgres directly (`psql "$DATABASE_URL"`) and
inspect the `users` table.

---

## 4. First-run seeding

The first user (`admin@ifpi.org` / `admin123`) is seeded automatically by
Alembic migration `initial_seed`. **Change this password immediately in
production** via the admin UI → Profile → Change Password.

Optional additional seeding:
- `python backend/scripts/seed_templates.py` — course templates for the
  Authoring Suite.
- Course marketplace catalogue starts empty. Admins can publish courses
  to the marketplace from the course detail page.

---

## 5. Deploy precheck

The `scripts/deploy_precheck.py` script runs at container boot (via the
supervisor's `command` for the backend program). It:

1. **Fails loudly** if any ⚠️ env var from §2 is missing or still set to
   the dev-only default (e.g. `dev-only-jwt-secret-…`).
2. **Runs Alembic migrations** with `alembic upgrade head`.
3. **Warms the connection pool** by opening + closing one Postgres
   connection so the first real request doesn't pay the cold-start
   penalty.

Run it manually to preview:

```bash
python backend/scripts/deploy_precheck.py
```

Exit code 0 = safe to serve. Non-zero = fix the reported issues before
serving traffic. See the script for the exhaustive list of validations.

---

## 6. Rollback playbook

If a deployment misbehaves:

1. **Frontend or backend regression** — Emergent Deploy tab → previous
   version → **Restore**.
2. **Migration regression** — connect to Postgres → `alembic downgrade -1`.
   Then restore the previous app version. **Warning:** downgrading past a
   data migration may lose data — always take a Postgres snapshot before
   deploying a schema change.
3. **Storage regression** — R2/S3 buckets are versioned by default when
   you enable versioning; restore individual objects from the console.
   Enable versioning on your bucket if not already.

### 6.1 Neon Point-in-Time Restore (recommended for accidental data loss)

Neon retains 7 days of WAL history on the free tier (30 on Pro), which
means you can restore the **entire database** to any second in that
window without a manual backup schedule.

1. **console.neon.tech** → your project → **Branches** → **Create branch**.
2. In the branch dialog:
   - Source: your primary branch (`main`).
   - **"Include data up to"** → pick the exact timestamp *before* the bad
     write / migration.
3. Copy the new branch's connection string.
4. Repoint `DATABASE_URL` in the Emergent Deploy tab to the new
   branch's URL, redeploy.
5. Verify the app is healthy against the restored data.
6. **Promote** the restored branch to primary in Neon
   (Branches → ⋯ → Set as default). Delete the old branch after you're
   confident the restore is good.

**Caveat:** Neon PITR restores the *database*, not object storage. If the
same incident deleted R2/S3 objects too, use R2 versioning restore
(step 3 above) alongside the DB rollback.

**Cost:** Restore branches count toward your Neon storage quota until
deleted. Delete the pre-incident primary once promotion is confirmed.

### 6.2 Admin lockout recovery (Iter 33b)

If the admin has lost their password AND the reset email is bouncing
(e.g. their SMTP relay is misconfigured or the domain was decommissioned):

```bash
# From the deploy container's shell:
ADMIN_RESCUE_SECRET="a-long-secret-only-you-know-at-least-16-chars" \
  python -m scripts.reset_admin_password
```

The script:
- Prompts twice for the new password (or reads it from `NEW_ADMIN_PASSWORD`
  env with `--from-env`).
- Sets `must_change_password=True` so the emergency password can't
  survive past first login.
- Revokes every active refresh token for the admin.
- Never logs the password value — only its length and source.

Communicate the new password to the admin via a **secure out-of-band
channel** (Signal, encrypted email, in person), then rotate
`ADMIN_RESCUE_SECRET` so the same value can't be used twice.

---

## 7. Known deploy-time gotchas| Symptom | Cause | Fix |
| --- | --- | --- |
| `sqlalchemy.exc.OperationalError: could not translate host name "None"` | `DATABASE_URL` not set | Set it (§2) |
| Login succeeds but subsequent requests 401 | `AUTH_COOKIE_SECURE=true` on HTTP-only preview URL | Either use HTTPS or flip to `false` for the preview host |
| Cert PDF downloads 500 | `STORAGE_BACKEND=s3` but no AWS creds | Set `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` |
| Emails silently vanish | No SMTP env set → falls back to stub | Set `SYSTEM_SMTP_*` env vars (§2) |
| CORS `Origin ... not allowed` | `ALLOWED_ORIGINS` doesn't include the frontend host | Add every prod hostname (including `www` variants) |
| First request cold-starts for 10+s | Postgres pool warm-up | The precheck script pre-warms; verify it ran |
| `alembic.util.exc.CommandError: Can't locate revision …` | You changed migrations after deploy but forgot to run `alembic upgrade head` | Run it manually, or redeploy — precheck does it |

---

## 8. What's NOT auto-migrated

- **Media uploads under `/app/backend/uploads/`** — local dev storage.
  If you have real uploads in local dev you want to keep, `s3 sync` them
  to your prod bucket before flipping `STORAGE_BACKEND` to `s3`.
- **SQLite data at `/app/backend/ifpi_lms.db`** — dev DB, do not migrate.
  Prod starts fresh from Alembic + `admin@ifpi.org` seed.

---

## 9. Contact

- Deployment issues: run `python backend/scripts/deploy_precheck.py`
  first, then check Emergent Support.
- Feature requests / bugs: see `memory/ROADMAP.md`.
- Architectural questions: see `docs/IFPI_VS_ERP360_ASSESSMENT.md`.
