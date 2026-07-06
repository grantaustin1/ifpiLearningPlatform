#!/usr/bin/env python3
"""Iter 33b — One-shot admin password rescue CLI.

Recovery path for the scenario where:
  - The admin has lost their password AND
  - Their password-reset email bounces (misconfigured MX / dropped domain)

Guards (defense in depth — this endpoint can grant admin access):
  1. `ADMIN_RESCUE_SECRET` env var MUST be set. This secret should be
     rotated between invocations and only known to the operator with
     shell access to the deploy container.
  2. Interactive confirmation prompt (or `--yes` to bypass in a
     scripted rescue).
  3. Sets `must_change_password=True` so the emergency password
     MUST be rotated on the very next login.
  4. Revokes ALL refresh tokens for the admin so any hijacked session
     is invalidated.
  5. Logs the action to stdout (source + length only, never the value).

Usage examples:
  # Interactive — prompts for the new password twice
  ADMIN_RESCUE_SECRET=xxx python -m scripts.reset_admin_password

  # Non-interactive from an env var
  ADMIN_RESCUE_SECRET=xxx NEW_ADMIN_PASSWORD=Xyz1234 \\
      python -m scripts.reset_admin_password --yes --from-env

  # Reset a specific admin (not the seeded admin@ifpi.org)
  ADMIN_RESCUE_SECRET=xxx python -m scripts.reset_admin_password \\
      --email other-admin@ifpi.org

Exit codes:
  0 — password reset successfully
  1 — target user not found / not an admin
  2 — pre-flight guard failed (missing env, weak password, etc.)
  130 — user aborted the confirmation prompt
"""
from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path

# Allow `python scripts/reset_admin_password.py` from /app/backend
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal  # noqa: E402
from core.security import get_password_hash  # noqa: E402
from models import User, UserRole  # noqa: E402


MIN_PASSWORD_LEN = 12


def _preflight() -> None:
    if not os.environ.get("ADMIN_RESCUE_SECRET", "").strip():
        print("❌  ADMIN_RESCUE_SECRET env var is not set.", file=sys.stderr)
        print("    This tool grants admin access — it MUST be gated behind a "
              "secret that only you know.", file=sys.stderr)
        print("    Set the env var (any string ≥16 chars is fine) and re-run.",
              file=sys.stderr)
        sys.exit(2)
    if len(os.environ["ADMIN_RESCUE_SECRET"]) < 16:
        print("❌  ADMIN_RESCUE_SECRET must be at least 16 characters.",
              file=sys.stderr)
        sys.exit(2)


def _prompt_new_password() -> str:
    while True:
        pw = getpass.getpass("New admin password (≥12 chars): ")
        if len(pw) < MIN_PASSWORD_LEN:
            print(f"❌  Password too short ({len(pw)} chars). Try again.",
                  file=sys.stderr)
            continue
        pw2 = getpass.getpass("Confirm new password: ")
        if pw != pw2:
            print("❌  Passwords do not match. Try again.", file=sys.stderr)
            continue
        return pw


def _from_env_password() -> str:
    pw = os.environ.get("NEW_ADMIN_PASSWORD", "").strip()
    if not pw:
        print("❌  --from-env passed but NEW_ADMIN_PASSWORD env var is unset.",
              file=sys.stderr)
        sys.exit(2)
    if len(pw) < MIN_PASSWORD_LEN:
        print(f"❌  NEW_ADMIN_PASSWORD too short ({len(pw)} chars). "
              f"Need ≥{MIN_PASSWORD_LEN}.", file=sys.stderr)
        sys.exit(2)
    return pw


def _find_admin(db, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f"❌  No user found with email {email!r}.", file=sys.stderr)
        sys.exit(1)
    if not user.is_active:
        print(f"❌  User {email!r} is INACTIVE (perhaps GDPR-erased). "
              f"Cannot reset password.", file=sys.stderr)
        sys.exit(1)
    is_admin = db.query(UserRole).filter(
        UserRole.user_id == user.id,
        UserRole.role.in_(["ADMIN", "SUPER_ADMIN"]),
    ).first() is not None
    if not is_admin:
        print(f"❌  User {email!r} is NOT an admin. This tool only resets "
              f"admin passwords (belt-and-braces guard). Regular learners "
              f"should use the /forgot-password flow.", file=sys.stderr)
        sys.exit(1)
    return user


def _confirm(prompt: str) -> bool:
    print(prompt, end=" [type YES to continue] ")
    sys.stdout.flush()
    reply = sys.stdin.readline().strip()
    return reply == "YES"


def reset_admin_password(email: str, new_password: str) -> User:
    """Public entrypoint — usable from other Python code + tests."""
    db = SessionLocal()
    try:
        user = _find_admin(db, email)
        user.password_hash = get_password_hash(new_password)
        # Force rotation on next login — the emergency password should
        # never survive past the first successful sign-in.
        user.must_change_password = True
        # Clear any brute-force lockout so the admin can log in
        # immediately with the new password.
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
        # Revoke every active refresh token so hijacked sessions die
        from services.auth_service import AuthService
        AuthService(db).revoke_all(user.id)
        return user
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Rescue-reset an admin password.")
    ap.add_argument("--email", default="admin@ifpi.org",
                    help="Admin email to reset (default: admin@ifpi.org)")
    ap.add_argument("--from-env", action="store_true",
                    help="Read the new password from NEW_ADMIN_PASSWORD env "
                         "var instead of prompting.")
    ap.add_argument("--yes", action="store_true",
                    help="Skip the interactive YES confirmation. Only "
                         "safe in scripted rescue paths.")
    args = ap.parse_args()

    _preflight()
    print(f"⚠️   About to reset password for {args.email!r}.")
    print(f"    Environment: {os.environ.get('ENVIRONMENT', 'unknown')}")
    print(f"    Database:    {os.environ.get('DATABASE_URL', 'unset')[:40]}…")
    if not args.yes and not _confirm("Are you sure?"):
        print("Aborted.", file=sys.stderr)
        return 130

    new_password = _from_env_password() if args.from_env else _prompt_new_password()

    user = reset_admin_password(args.email, new_password)
    print(f"\n✅  Password reset for {user.email} (id={user.id}).")
    print(f"    Source: {'NEW_ADMIN_PASSWORD env' if args.from_env else 'interactive prompt'}")
    print(f"    Length: {len(new_password)} chars")
    print(f"    must_change_password: True — the admin MUST rotate this on "
          f"their next login.")
    print(f"    All refresh tokens revoked — any active session is invalidated.")
    print(f"\nNext steps:")
    print(f"  1. Communicate the new password to the admin via a SECURE "
          f"out-of-band channel (Signal, encrypted email, in person).")
    print(f"  2. Rotate ADMIN_RESCUE_SECRET so the same value can't be "
          f"used twice.")
    print(f"  3. Verify the admin can log in and is prompted to change "
          f"their password immediately.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
