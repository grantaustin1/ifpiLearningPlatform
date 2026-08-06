# IFPI Learning Platform — Test Credentials

Both accounts live in the default "IFPI Main Academy" tenant (`organization_id=1`).

## UAT Sandbox tenant (org `uat-sandbox`, created 2026-07-30)
Isolated tenant for team UAT. See `/app/docs/UAT_TESTER_GUIDE.md`.
- UAT Admin: `uat-admin@ifpi.org` / `UatAdmin!2026` (ADMIN, no forced password change, email pre-verified)
- UAT Learner: `uat-learner@ifpi.org` / `UatLearner!2026` (LEARNER)
- Setup script (idempotent): `python /app/backend/scripts/setup_uat.py`
- Factory reset (restores pre-UAT DB snapshot): `bash /app/scripts/reset_uat.sh`

## Admin
- Email: `admin@ifpi.org`
- Password: `admin123`
- Role: `ADMIN`
- **Iter 32 — `must_change_password=True`**: On first login the app
  redirects to `/change-password?forced=1`. If your test needs the
  admin to reach the dashboard without triggering this gate, either:
  1. Clear the flag manually: `UPDATE users SET must_change_password=0
     WHERE email='admin@ifpi.org'`, or
  2. Complete the change-password form once (backend/frontend both
     honour the flag).
- 2FA (TOTP): **DISABLED** by default. Test files (`test_iteration30i_totp.py`) enable it,
  run the flow, and re-disable at teardown. If a test aborts mid-flow, run the following
  to recover:
  ```
  cd /app/backend && python -c "
  from core.database import SessionLocal; from models import User
  db=SessionLocal(); u=db.query(User).filter_by(email='admin@ifpi.org').first()
  u.totp_secret_enc=None; u.totp_enabled_at=None; u.totp_recovery_codes=[]
  db.commit(); print('2FA cleared')"
  ```
- Capabilities: full course/exam CRUD, AI builder, analytics, user list, billing console.

## Learner
- Email: `learner@ifpi.org`
- Password: `learner123`
- Role: `LEARNER`
- Capabilities: browse catalog, enrol in courses, take exams, view own certificates.

## Self-registration
Any visitor can register at `/register`. New accounts are ALWAYS created as `LEARNER` —
admin elevation is invite-only (no UI yet, must be done via DB or `/api/admin/users` POST in v2).

## SSO bridge (disabled in v1)
When `SSO_ENABLED=true` and `ERP360_SSO_SHARED_SECRET` is set, ERP360 can mint a
short-lived JWT for the current user and POST it to `/api/auth/sso-exchange`.

## Billing (stub in v1)
Subscribing to a paid course auto-activates without real payment (stub mode).
Set `BILLING_LIVE_MODE=true` + `ERP360_BASE_URL` + `ERP360_BILLING_WEBHOOK_SECRET`
to route through ERP360's lite-billing module.
