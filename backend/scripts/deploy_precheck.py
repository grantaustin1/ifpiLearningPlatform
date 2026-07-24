#!/usr/bin/env python3
"""Iter 32 — Production deployment precheck.

Runs at container boot. Fails loudly if any required-in-prod env var
is missing or set to a dev-only default. When ENVIRONMENT!=production
this script is a soft advisor (prints warnings but does not exit 1).

Also runs `alembic upgrade head` and pre-warms the Postgres pool so
the first real request doesn't pay the cold-start penalty.

Usage:
    python backend/scripts/deploy_precheck.py [--strict]

Exit codes:
    0  — safe to serve traffic
    1  — one or more blockers; DO NOT serve traffic
    2  — internal error (couldn't parse env, DB unreachable, etc.)

See DEPLOYMENT.md for the full env-var reference and remediation steps.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # /app/backend

# ── dev-only sentinel values that MUST be rotated ───────────────
DEV_ONLY_SECRETS = {
    "JWT_SECRET": (
        "dev-only-jwt-secret-change-in-production-please-7f3a8b2c",
        "dev-secret",
    ),
    "SMTP_ENCRYPTION_KEY": (
        "mltTKVHxmg2Ek88Jvbpy78aQlgbc4e03DliF5n-tvQQ=",
    ),
}


class Result:
    """A single validation outcome."""
    def __init__(self, ok: bool, level: str, key: str, message: str):
        self.ok = ok
        self.level = level  # BLOCKER | WARN | INFO
        self.key = key
        self.message = message

    def render(self) -> str:
        icon = {"BLOCKER": "❌", "WARN": "⚠️ ", "INFO": "ℹ️ "}[self.level]
        return f"  {icon}  [{self.key}] {self.message}"


# ── validation rules ────────────────────────────────────────────
def _val(key: str) -> str:
    return (os.environ.get(key) or "").strip()


def check_environment_flag() -> Result:
    v = _val("ENVIRONMENT").lower()
    if v == "production":
        return Result(True, "INFO", "ENVIRONMENT", "production")
    if v in ("development", "dev", "staging", "test"):
        return Result(True, "WARN", "ENVIRONMENT",
                      f"'{v}' — soft-advisor mode; blockers will be "
                      "downgraded to warnings. Set to 'production' to "
                      "enforce all deploy blockers.")
    # Empty/unset OR unknown value → treated as production (fail-closed)
    return Result(False, "WARN", "ENVIRONMENT",
                  f"'{v or 'unset'}' — treating as PRODUCTION (fail-closed). "
                  "Set ENVIRONMENT=development to unlock soft-advisor mode.")


def check_jwt_secret() -> Result:
    v = _val("JWT_SECRET")
    if not v:
        return Result(False, "BLOCKER", "JWT_SECRET", "unset")
    for bad in DEV_ONLY_SECRETS["JWT_SECRET"]:
        if v == bad or "dev-only" in v:
            return Result(False, "BLOCKER", "JWT_SECRET",
                          "still the dev-only default; rotate with "
                          "`python -c \"import secrets; "
                          "print(secrets.token_urlsafe(48))\"`")
    if len(v) < 32:
        return Result(False, "BLOCKER", "JWT_SECRET",
                      f"too short ({len(v)} chars) — need ≥32")
    return Result(True, "INFO", "JWT_SECRET", f"OK ({len(v)} chars)")


def check_smtp_encryption_key() -> Result:
    v = _val("SMTP_ENCRYPTION_KEY")
    if not v:
        return Result(False, "BLOCKER", "SMTP_ENCRYPTION_KEY", "unset")
    if v in DEV_ONLY_SECRETS["SMTP_ENCRYPTION_KEY"]:
        return Result(False, "BLOCKER", "SMTP_ENCRYPTION_KEY",
                      "still the dev-only default; rotate with "
                      "`python -c \"from cryptography.fernet import Fernet; "
                      "print(Fernet.generate_key().decode())\"`")
    return Result(True, "INFO", "SMTP_ENCRYPTION_KEY", "OK")


def check_database_url() -> Result:
    v = _val("DATABASE_URL")
    if not v:
        return Result(False, "BLOCKER", "DATABASE_URL", "unset")
    if v.startswith("sqlite"):
        return Result(False, "BLOCKER", "DATABASE_URL",
                      f"points to SQLite ({v}) — production requires "
                      "postgresql:// (see DEPLOYMENT.md §3.1)")
    if not v.startswith(("postgresql://", "postgresql+psycopg2://",
                         "postgresql+asyncpg://")):
        return Result(False, "BLOCKER", "DATABASE_URL",
                      f"unsupported scheme in {v[:20]}…; expected "
                      "postgresql://")
    return Result(True, "INFO", "DATABASE_URL", "Postgres detected")


def check_cookie_flags() -> list[Result]:
    out = []
    mode = _val("AUTH_COOKIE_MODE").lower()
    if mode != "on":
        out.append(Result(False, "BLOCKER", "AUTH_COOKIE_MODE",
                          f"expected 'on', got {mode or 'unset'}"))
    else:
        out.append(Result(True, "INFO", "AUTH_COOKIE_MODE", "on"))
    secure = _val("AUTH_COOKIE_SECURE").lower()
    if secure != "true":
        out.append(Result(False, "BLOCKER", "AUTH_COOKIE_SECURE",
                          f"expected 'true', got {secure or 'unset'} — "
                          "HTTPS-only cookies required in prod"))
    else:
        out.append(Result(True, "INFO", "AUTH_COOKIE_SECURE", "true"))
    allow_test = _val("ALLOW_TEST_TOKEN_HEADER").lower()
    if allow_test == "true":
        out.append(Result(False, "BLOCKER", "ALLOW_TEST_TOKEN_HEADER",
                          "is 'true' — bypasses cookie-only auth. MUST "
                          "be 'false' in prod"))
    else:
        out.append(Result(True, "INFO", "ALLOW_TEST_TOKEN_HEADER",
                          f"'{allow_test or 'unset'}' (safe)"))
    return out


def check_cors() -> Result:
    v = _val("ALLOWED_ORIGINS")
    if not v:
        return Result(False, "BLOCKER", "ALLOWED_ORIGINS",
                      "unset — must list the exact prod frontend origins")
    if v == "*":
        return Result(False, "BLOCKER", "ALLOWED_ORIGINS",
                      "is '*' — wildcard is dangerous with credentialed "
                      "cookies. Restrict to explicit origins.")
    origins = [o.strip() for o in v.split(",") if o.strip()]
    for o in origins:
        if not o.startswith(("http://", "https://")):
            return Result(False, "BLOCKER", "ALLOWED_ORIGINS",
                          f"origin '{o}' missing scheme (http:// or https://)")
        if o.startswith("http://") and "localhost" not in o and "127.0.0.1" not in o:
            return Result(False, "WARN", "ALLOWED_ORIGINS",
                          f"origin '{o}' is HTTP — cookies with Secure=true "
                          "won't be sent to HTTP hosts")
    return Result(True, "INFO", "ALLOWED_ORIGINS",
                  f"{len(origins)} origin(s) configured")


def check_storage() -> list[Result]:
    out = []
    backend = _val("STORAGE_BACKEND").lower()
    if backend not in ("s3", "gcs"):
        out.append(Result(False, "BLOCKER", "STORAGE_BACKEND",
                          f"expected 's3' or 'gcs', got '{backend or 'unset'}'"
                          " — local disk won't survive pod restarts"))
        return out
    out.append(Result(True, "INFO", "STORAGE_BACKEND", backend))
    if backend == "s3":
        for k in ("S3_BUCKET", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
            if not _val(k):
                out.append(Result(False, "BLOCKER", k, "unset"))
            else:
                out.append(Result(True, "INFO", k, "set"))
    return out


def check_smtp() -> Result:
    if not _val("SYSTEM_SMTP_HOST"):
        return Result(False, "WARN", "SYSTEM_SMTP_HOST",
                      "unset — no system SMTP relay. Per-tenant SMTP or "
                      "the ERP360 bridge must be configured, otherwise "
                      "outgoing emails will fall through to the stub.")
    for k in ("SYSTEM_SMTP_PORT", "SYSTEM_SMTP_USERNAME",
              "SYSTEM_SMTP_PASSWORD", "SYSTEM_SMTP_FROM_EMAIL"):
        if not _val(k):
            return Result(False, "BLOCKER", k,
                          "unset — required alongside SYSTEM_SMTP_HOST")
    return Result(True, "INFO", "SYSTEM_SMTP_HOST",
                  f"{_val('SYSTEM_SMTP_HOST')}:{_val('SYSTEM_SMTP_PORT')}")


def check_public_base_url() -> Result:
    v = _val("PUBLIC_BASE_URL")
    if not v:
        return Result(False, "BLOCKER", "PUBLIC_BASE_URL",
                      "unset — used in email links, cert verify URLs, "
                      "OG social previews. Set to the prod frontend URL.")
    if "preview.emergentagent.com" in v:
        return Result(False, "BLOCKER", "PUBLIC_BASE_URL",
                      "still points to the preview URL — set to the "
                      "prod domain")
    if not v.startswith("https://"):
        return Result(False, "BLOCKER", "PUBLIC_BASE_URL",
                      f"is '{v}' — must be an HTTPS URL")
    return Result(True, "INFO", "PUBLIC_BASE_URL", v)


def check_llm_key() -> Result:
    v = _val("EMERGENT_LLM_KEY")
    if not v:
        return Result(False, "WARN", "EMERGENT_LLM_KEY",
                      "unset — AI Authoring Suite features will fail. "
                      "Get one from Emergent Profile → Universal Key")
    return Result(True, "INFO", "EMERGENT_LLM_KEY", "set")


def check_seed_admin_password() -> Result:
    """Iter 33 — Prevent the seed script from generating an admin
    with the well-known `admin123` password in prod."""
    v = _val("SEED_ADMIN_PASSWORD")
    if not v:
        return Result(False, "BLOCKER", "SEED_ADMIN_PASSWORD",
                      "unset — seed_minimal would fall back to a "
                      "well-known default password. Set to a strong "
                      "value; the seeded admin is created with "
                      "must_change_password=True regardless, so this "
                      "is defense-in-depth.")
    if v == "admin123" or len(v) < 12:
        return Result(False, "BLOCKER", "SEED_ADMIN_PASSWORD",
                      f"weak value ({len(v)} chars). Use ≥12 chars.")
    return Result(True, "INFO", "SEED_ADMIN_PASSWORD",
                  f"set ({len(v)} chars)")


# ── side-effects ────────────────────────────────────────────────
def run_alembic() -> Result:
    """Idempotent: `alembic upgrade head`."""
    try:
        r = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=90,
        )
        if r.returncode != 0:
            return Result(False, "BLOCKER", "alembic upgrade",
                          f"failed: {r.stderr.strip()[:200]}")
        return Result(True, "INFO", "alembic upgrade",
                      "schema at head")
    except FileNotFoundError:
        return Result(False, "BLOCKER", "alembic upgrade",
                      "`alembic` binary not on PATH")
    except subprocess.TimeoutExpired:
        return Result(False, "BLOCKER", "alembic upgrade",
                      "timed out after 90s")


def warm_db_pool() -> Result:
    """Open + close one Postgres connection so first request is warm."""
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from core.database import engine  # noqa: E402
        with engine.connect() as conn:
            from sqlalchemy import text  # noqa: E402
            conn.execute(text("SELECT 1"))
        return Result(True, "INFO", "db-pool", "warmed (1 conn round-trip)")
    except Exception as e:  # noqa: BLE001
        return Result(False, "BLOCKER", "db-pool",
                      f"cannot reach DB: {str(e)[:150]}")


# ── entrypoint ──────────────────────────────────────────────────
def main() -> int:
    strict = "--strict" in sys.argv
    print("─" * 60)
    print("IFPI Deployment Precheck")
    print(f"  ENVIRONMENT = {_val('ENVIRONMENT') or 'unset'}")
    print("─" * 60)

    # Iter 32 — Fail-closed on unset ENVIRONMENT.
    # A missing ENVIRONMENT env var USED to downgrade blockers to
    # warnings, meaning a deploy that forgot to set it would boot with
    # dev secrets. Now we treat empty/unset as production so forgetting
    # the flag = safe (deploy refuses to boot), not dangerous.
    # Explicit ENVIRONMENT=development or ENVIRONMENT=staging is
    # required to unlock the soft-advisor mode.
    env = _val("ENVIRONMENT").lower()
    if env in ("development", "dev", "staging", "test"):
        is_prod = False or strict  # explicit dev-ish → soft mode
    else:
        is_prod = True  # unset OR "production" OR anything else → fail-closed

    results: list[Result] = []
    results.append(check_environment_flag())
    results.append(check_jwt_secret())
    results.append(check_smtp_encryption_key())
    results.append(check_database_url())
    results.extend(check_cookie_flags())
    results.append(check_cors())
    results.extend(check_storage())
    results.append(check_smtp())
    results.append(check_public_base_url())
    results.append(check_llm_key())
    results.append(check_seed_admin_password())

    # is_prod already computed at top of main() — fail-closed on unset ENVIRONMENT

    blockers = [r for r in results if r.level == "BLOCKER"]
    warns = [r for r in results if r.level == "WARN"]

    # In prod, ALL blockers exit non-zero. In non-prod, blockers become
    # warnings so the dev container still boots.
    if not is_prod and blockers:
        print("Config check (non-prod — blockers downgraded to warnings):\n")
        for r in results:
            print(r.render())
        print(f"\n  {len(blockers)} would-be blocker(s), {len(warns)} warning(s).")
        print("  Set ENVIRONMENT=production (or pass --strict) to enforce.")
        print("─" * 60)
        # Still run migrations + warm pool so the dev boot succeeds
        results.append(run_alembic())
        results.append(warm_db_pool())
        return 0

    # Prod path: enforce blockers first, then run side-effects
    if blockers:
        print("BLOCKERS — refusing to serve traffic:\n")
        for r in results:
            print(r.render())
        print("─" * 60)
        print(f"❌  {len(blockers)} blocker(s). See DEPLOYMENT.md.")
        return 1

    # No blockers — run side-effects
    results.append(run_alembic())
    results.append(warm_db_pool())

    # Re-check blockers after side-effects (migration/db could fail)
    blockers = [r for r in results if r.level == "BLOCKER"]
    for r in results:
        print(r.render())
    print("─" * 60)
    if blockers:
        print(f"❌  {len(blockers)} blocker(s) during boot.")
        return 1
    if warns:
        print(f"✅  Ready to serve. ({len(warns)} warning(s) — non-blocking.)")
    else:
        print("✅  All green. Ready to serve traffic.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
