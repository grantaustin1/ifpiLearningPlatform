"""Auth routes: register, login, refresh, logout, /me, and the SSO bridge."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from auth.cookies import (
    REFRESH_COOKIE, clear_auth_cookies, generate_csrf_token, set_auth_cookie,
    set_csrf_cookie, set_refresh_cookie, should_include_token_in_body,
)
from auth.dependencies import CurrentUser, get_current_user
from core.config import settings
from core.database import get_db
from core.role_registry import normalize_role_names
from schemas import (
    ChangePasswordRequest, ForgotPasswordRequest, LoginRequest, LoginResponse,
    RegisterRequest, ResetPasswordRequest, UserOut,
)
from services.auth_service import AuthService
from services.sso_service import SSOService

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _to_user_out(user) -> UserOut:
    roles = normalize_role_names([ur.role for ur in user.user_roles]) or ["LEARNER"]
    return UserOut(
        id=user.id, email=user.email, name=user.name,
        organization_id=user.organization_id, roles=roles,
        points=user.points or 0,
        must_change_password=bool(getattr(user, "must_change_password", False)),
    )


def _login_response(response: Response, user, access: str, refresh: str,
                    request: Request | None = None) -> LoginResponse:
    import os
    set_auth_cookie(response, access)
    set_refresh_cookie(response, refresh)
    set_csrf_cookie(response, generate_csrf_token())
    # Iter 22 — The `X-Return-Token: true` header used to be honoured
    # unconditionally as a test/SDK affordance. That was effectively a
    # backdoor in production: an XSS payload could set the header on a
    # login retry and exfiltrate the JWT out of the HttpOnly cookie
    # jar. It is now gated behind `ALLOW_TEST_TOKEN_HEADER=true`, which
    # is set ONLY in development/test environments. Production deploys
    # do not set the env var, so the header is inert.
    test_bypass_allowed = os.environ.get("ALLOW_TEST_TOKEN_HEADER", "").lower() == "true"
    return_token = should_include_token_in_body() or (
        test_bypass_allowed and request is not None and
        request.headers.get("x-return-token", "").lower() == "true"
    )
    return LoginResponse(
        access_token=access if return_token else None,
        expires_in=settings.jwt_expiration_minutes * 60,
        user=_to_user_out(user),
    )


@router.post("/register", response_model=LoginResponse)
def register(body: RegisterRequest, request: Request, response: Response,
             db: Session = Depends(get_db)):
    svc = AuthService(db)
    user = svc.register(body.email, body.password, body.name)
    access, refresh = svc.issue_tokens(user)
    return _login_response(response, user, access, refresh, request=request)


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response,
          db: Session = Depends(get_db)):
    svc = AuthService(db)
    user = svc.login(body.email, body.password)
    # Iter 30i — if 2FA is enabled, don't issue tokens yet. Return an
    # opaque challenge_id that the frontend exchanges for tokens after
    # collecting the 6-digit code.
    if user.totp_secret_enc and user.totp_enabled_at:
        from routers.totp import create_challenge
        cid, expires_in = create_challenge(user.id)
        return {"requires_2fa": True, "challenge_id": cid,
                "expires_in": expires_in}
    access, refresh = svc.issue_tokens(user)
    return _login_response(response, user, access, refresh, request=request)


@router.post("/refresh", response_model=LoginResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        # Allow Bearer fallback
        authz = request.headers.get("authorization", "")
        if authz.lower().startswith("bearer "):
            token = authz.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    access, new_refresh, user = AuthService(db).rotate_refresh(token)
    return _login_response(response, user, access, new_refresh, request=request)


@router.post("/logout")
def logout(response: Response, current: CurrentUser = Depends(get_current_user),
           db: Session = Depends(get_db)):
    AuthService(db).revoke_all(current.id)
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from models import User
    # API tokens (Iter 21) carry a negative `id` and don't have a User row —
    # return the synthetic principal data directly.
    if current.id < 0:
        return UserOut(
            id=current.id, email=current.email, name=current.name,
            organization_id=current.organization_id, roles=current.roles,
            points=0,
        )
    user = db.query(User).filter(User.id == current.id).first()
    return _to_user_out(user)


# ── SSO bridge (stubbed until ERP360 is wired) ───────────────────────
@router.get("/sso-status")
def sso_status():
    """Public endpoint — the login page calls this on mount to decide whether
    to render the "Continue with ERP360" button. Returns the redirect URL
    where ERP360 will mint the token and bounce back to IFPI."""
    enabled = settings.sso_enabled and bool(settings.erp360_sso_shared_secret)
    initiate_url = None
    if enabled and settings.erp360_base_url:
        # ERP360 hands off to IFPI by redirecting back to /sso/return?erp_token=...
        initiate_url = (
            settings.erp360_base_url.rstrip("/")
            + "/api/sso/mint?return_to=/sso/return&app=ifpi"
        )
    return {"enabled": enabled, "initiate_url": initiate_url}


@router.post("/sso-exchange", response_model=LoginResponse)
def sso_exchange(payload: dict, response: Response, request: Request,
                 db: Session = Depends(get_db)):
    """Inbound SSO from ERP360. Body: {"erp_token": "..."}.
    Returns same shape as login so the frontend handles it identically.
    """
    sso = SSOService(db)
    if not sso.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="SSO is not enabled. Set SSO_ENABLED=true and ERP360_SSO_SHARED_SECRET to activate.",
        )
    token = payload.get("erp_token")
    if not token:
        raise HTTPException(status_code=400, detail="erp_token is required")
    claims = sso.verify_inbound_token(token)
    user, created = sso.jit_provision(claims)

    # Audit — split create vs login so admins can see provisioning events
    from services import audit_service

    class _SSOActor:
        id = user.id
        organization_id = user.organization_id

    actor = _SSOActor()
    if created:
        audit_service.record(
            db, actor, "SSO_USER_PROVISIONED",
            target_type="user", target_id=str(user.id),
            metadata={"erp360_user_id": user.erp360_user_id,
                      "email": user.email,
                      "roles": [ur.role for ur in user.user_roles]},
            request=request,
        )
    audit_service.record(
        db, actor, "SSO_LOGIN_SUCCESS",
        target_type="user", target_id=str(user.id),
        metadata={"erp360_user_id": user.erp360_user_id, "email": user.email},
        request=request,
    )
    db.commit()

    access, refresh = AuthService(db).issue_tokens(user)
    return _login_response(response, user, access, refresh, request=request)


# ── Iter 32 · Password change + reset ────────────────────────────────
@router.post("/change-password")
def change_password(body: ChangePasswordRequest,
                    current: CurrentUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Self-service password change. Verifies the old password, sets the
    new one, clears the `must_change_password` flag, and revokes all
    active refresh tokens so other devices are logged out.
    """
    if current.id < 0:
        raise HTTPException(status_code=400,
                            detail="API token principals cannot change passwords")
    AuthService(db).change_password(
        user_id=current.id,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return {"ok": True}


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, request: Request,
                    db: Session = Depends(get_db)):
    """Emails a single-use reset link if the address matches an active
    user. Always returns 200 (enumeration guard) — the response is
    identical whether the email was found or not.
    """
    from services.mail_service import MailService
    ip = (request.headers.get("x-forwarded-for", "")
          or (request.client.host if request.client else "")).split(",")[0].strip()
    result = AuthService(db).request_password_reset(body.email, ip=ip)
    if result:
        user, raw = result
        base = (settings.public_base_url or "").rstrip("/")
        link = f"{base}/reset-password/{raw}"
        html = (
            f"<h2>Reset your IFPI Learning password</h2>"
            f"<p>Hi {user.name or user.email},</p>"
            f"<p>Someone (hopefully you) asked to reset your password. "
            f"Click the link below within the next hour:</p>"
            f"<p><a href='{link}' style='background:#4f46e5;color:#fff;"
            f"padding:10px 16px;border-radius:8px;text-decoration:none;"
            f"font-weight:600;display:inline-block'>Reset password</a></p>"
            f"<p style='color:#64748b;font-size:12px;'>Or paste this URL: "
            f"<code>{link}</code></p>"
            f"<p style='color:#94a3b8;font-size:12px'>If you didn't request "
            f"this, ignore this email — nothing will change.</p>"
        )
        text = f"Reset your IFPI password: {link}\n\nThe link expires in 1 hour."
        MailService(db).send_email(
            to_email=user.email, to_name=user.name or user.email,
            subject="Reset your IFPI Learning password",
            body_html=html, body_text=text, template="password_reset",
            organization_id=user.organization_id, user_id=user.id,
        )
        db.commit()
    # Constant response regardless of match
    return {"ok": True, "message":
            "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, request: Request,
                   response: Response, db: Session = Depends(get_db)):
    """Consume a reset token + set a new password. On success, logs the
    user in immediately (cookies set) so they don't have to re-enter
    the credential they just picked.
    """
    user = AuthService(db).consume_password_reset(body.token, body.new_password)
    access, refresh = AuthService(db).issue_tokens(user)
    return _login_response(response, user, access, refresh, request=request)
