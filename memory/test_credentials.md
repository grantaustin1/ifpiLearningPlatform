# IFPI Learning Platform — Test Credentials

Both accounts live in the default "IFPI Main Academy" tenant (`organization_id=1`).

## Admin
- Email: `admin@ifpi.org`
- Password: `admin123`
- Role: `ADMIN`
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
