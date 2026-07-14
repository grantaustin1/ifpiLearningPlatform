"""§7.4 per-org SSO enablement + §7.2 verified-email link tightening.

Locks in these invariants:

**§7.4 — Per-org SSO gate**
- SSO refuses (403) if the target org has `integrations.erp360.sso_enabled=False`
  AND the legacy `SSO_ENABLED` env is also false.
- SSO accepts if per-org `sso_enabled=true`, regardless of env.
- SSO accepts (legacy fallback) if per-org is false but env is true —
  logs a warning during the migration window.

**§7.2 — Verified-email link tightening**
- If a native IFPI account exists for the email being SSO'd,
  auto-linking requires BOTH:
    (a) native `email_verified_at IS NOT NULL`
    (b) ERP360 claim asserts `email_verified: true`
- Either side unverified → refuse the auto-link with 409.
- Both verified → link succeeds and `erp360_user_id` is stamped
  authoritatively.
"""
from __future__ import annotations

import os
import time
import uuid

import jwt
import pytest
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or os.environ.get("TEST_BASE_URL", "http://localhost:8001")


def _mint(sub: int, email: str, *, org_slug: str | None = None,
          email_verified: bool | None = None, name: str = "Test User",
          roles: list | None = None) -> str:
    secret = os.environ["ERP360_SSO_SHARED_SECRET"]
    now = int(time.time())
    claims = {
        "iss": "erp360",
        "aud": "ifpi-lms",
        "sub": str(sub),
        "email": email,
        "name": name,
        "roles": roles or ["TRAINER"],
        "iat": now,
        "exp": now + 300,
        "jti": uuid.uuid4().hex,
    }
    if org_slug is not None:
        claims["org_slug"] = org_slug
    if email_verified is not None:
        claims["email_verified"] = email_verified
    return jwt.encode(claims, secret, algorithm="HS256")


# ─── §7.4 — Per-org enablement ────────────────────────────────────────
class TestPerOrgSsoEnablement:
    """§7.4 — the global SSO_ENABLED env flag is a legacy fallback;
    per-org `integrations.erp360.sso_enabled` is authoritative."""

    def test_per_org_disabled_and_env_disabled_returns_403(self):
        """Direct service-level test (isolated from the shared preview
        env which has `SSO_ENABLED=true`)."""
        from core.database import SessionLocal
        from models import Organization
        from services.sso_service import SSOService
        from fastapi import HTTPException

        # Monkey-patch settings.sso_enabled → False for this call
        from core import config as _cfg
        original = _cfg.settings.sso_enabled
        _cfg.settings.sso_enabled = False
        db = SessionLocal()
        try:
            svc = SSOService(db)
            # Use an org whose erp360.sso_enabled is definitely False
            org = db.query(Organization).filter(
                Organization.slug == "ifpi-main"
            ).first()
            assert org is not None
            assert org.erp360_sso_enabled is False
            claims = {
                "sub": "999901",
                "email": f"gate-off-{uuid.uuid4().hex[:8]}@ifpi.test",
                "roles": ["TRAINER"],
                "org_slug": org.slug,
                "email_verified": True,
            }
            with pytest.raises(HTTPException) as ei:
                svc.jit_provision(claims)
            assert ei.value.status_code == 403
            assert "sso_enabled" in ei.value.detail.lower()
        finally:
            _cfg.settings.sso_enabled = original
            db.close()

    def test_per_org_enabled_accepts_even_when_env_off(self):
        """Flip per-org true, env false → accept."""
        from core.database import SessionLocal
        from models import Organization
        from services.sso_service import SSOService
        from core import config as _cfg

        original = _cfg.settings.sso_enabled
        _cfg.settings.sso_enabled = False
        db = SessionLocal()
        try:
            org = db.query(Organization).filter(
                Organization.slug == "ifpi-main"
            ).first()
            # Enable per-org (only for this test — restored in finally)
            original_integrations = org.integrations or {}
            org.integrations = {**original_integrations,
                                "erp360": {"connected": True,
                                           "sso_enabled": True}}
            db.commit()
            try:
                svc = SSOService(db)
                sub = 900_800_000 + int(uuid.uuid4().int % 1_000_000)
                claims = {
                    "sub": str(sub),
                    "email": f"gate-on-{uuid.uuid4().hex[:8]}@ifpi.test",
                    "roles": ["TRAINER"],
                    "org_slug": org.slug,
                    "email_verified": True,
                }
                user, created = svc.jit_provision(claims)
                assert created is True
                assert user.erp360_user_id == sub
            finally:
                org.integrations = original_integrations
                db.commit()
        finally:
            _cfg.settings.sso_enabled = original
            db.close()

    def test_legacy_env_flag_still_works(self):
        """Preview default: per-org false, env true → accept (with warn)."""
        from core.database import SessionLocal
        from services.sso_service import SSOService

        db = SessionLocal()
        try:
            # Preview .env has SSO_ENABLED=true — this is the legacy path.
            svc = SSOService(db)
            sub = 900_810_000 + int(uuid.uuid4().int % 1_000_000)
            email = f"legacy-env-{uuid.uuid4().hex[:8]}@ifpi.test"
            claims = {
                "sub": str(sub),
                "email": email,
                "roles": ["TRAINER"],
                # no org_slug — falls back to default org
                "email_verified": True,
            }
            user, created = svc.jit_provision(claims)
            assert created is True
        finally:
            db.close()


# ─── §7.2 — Verified-email link tightening ────────────────────────────
class TestVerifiedEmailLinkTightening:
    """§7.2 — Native-user linking requires verified email on BOTH sides."""

    def _make_native_user(self, email: str, verified: bool):
        from core.database import SessionLocal
        from models import Organization, User
        from datetime import datetime, timezone
        db = SessionLocal()
        try:
            org = db.query(Organization).filter(
                Organization.slug == "ifpi-main"
            ).first()
            u = User(
                email=email, name="Native", organization_id=org.id,
                is_active=True,
                email_verified_at=datetime.now(timezone.utc) if verified else None,
            )
            db.add(u)
            db.commit()
            return u.id
        finally:
            db.close()

    def test_refuse_link_when_claim_says_email_not_verified(self):
        """Native verified + claim `email_verified: false` → 409."""
        from services.sso_service import SSOService
        from core.database import SessionLocal
        from fastapi import HTTPException

        email = f"link-claim-off-{uuid.uuid4().hex[:8]}@ifpi.test"
        self._make_native_user(email, verified=True)

        db = SessionLocal()
        try:
            svc = SSOService(db)
            sub = 900_820_000 + int(uuid.uuid4().int % 1_000_000)
            with pytest.raises(HTTPException) as ei:
                svc.jit_provision({
                    "sub": str(sub),
                    "email": email,
                    "roles": ["TRAINER"],
                    "email_verified": False,
                })
            assert ei.value.status_code == 409
            assert "email_verified" in ei.value.detail
        finally:
            db.close()

    def test_refuse_link_when_claim_omits_email_verified(self):
        """Native verified + claim omits `email_verified` → 409
        (fail-closed: absent field is treated as unverified)."""
        from services.sso_service import SSOService
        from core.database import SessionLocal
        from fastapi import HTTPException

        email = f"link-claim-missing-{uuid.uuid4().hex[:8]}@ifpi.test"
        self._make_native_user(email, verified=True)

        db = SessionLocal()
        try:
            svc = SSOService(db)
            sub = 900_830_000 + int(uuid.uuid4().int % 1_000_000)
            with pytest.raises(HTTPException) as ei:
                svc.jit_provision({
                    "sub": str(sub),
                    "email": email,
                    "roles": ["TRAINER"],
                    # no email_verified key at all
                })
            assert ei.value.status_code == 409
        finally:
            db.close()

    def test_accept_link_when_both_sides_verified(self):
        """Native verified + claim verified → auto-link succeeds."""
        from services.sso_service import SSOService
        from core.database import SessionLocal

        email = f"link-both-ok-{uuid.uuid4().hex[:8]}@ifpi.test"
        native_id = self._make_native_user(email, verified=True)

        db = SessionLocal()
        try:
            svc = SSOService(db)
            sub = 900_840_000 + int(uuid.uuid4().int % 1_000_000)
            user, created = svc.jit_provision({
                "sub": str(sub),
                "email": email,
                "roles": ["TRAINER"],
                "email_verified": True,
            })
            # Linked to existing native user, not created
            assert created is False
            assert user.id == native_id
            assert user.erp360_user_id == sub
        finally:
            db.close()

    def test_refuse_link_when_native_unverified(self):
        """Native unverified + claim verified → still 409 (§7.2 original)."""
        from services.sso_service import SSOService
        from core.database import SessionLocal
        from fastapi import HTTPException

        email = f"link-native-off-{uuid.uuid4().hex[:8]}@ifpi.test"
        self._make_native_user(email, verified=False)

        db = SessionLocal()
        try:
            svc = SSOService(db)
            sub = 900_850_000 + int(uuid.uuid4().int % 1_000_000)
            with pytest.raises(HTTPException) as ei:
                svc.jit_provision({
                    "sub": str(sub),
                    "email": email,
                    "roles": ["TRAINER"],
                    "email_verified": True,
                })
            assert ei.value.status_code == 409
            assert "not verified" in ei.value.detail.lower()
        finally:
            db.close()
