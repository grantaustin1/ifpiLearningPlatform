"""Iteration 5 features: cert preview, file uploads, slide comments,
multi-tenant academy management (SUPER_ADMIN), public academy portals."""
from fastapi import APIRouter

preview_router = APIRouter(prefix="/api/admin/cert-preview", tags=["Cert preview"])
uploads_router = APIRouter(prefix="/api/uploads", tags=["Uploads"])
comments_router = APIRouter(prefix="/api", tags=["Comments"])
academies_router = APIRouter(prefix="/api/academies", tags=["Academies"])
portal_router = APIRouter(prefix="/api/portal", tags=["Public portal"])


def sign_outgoing_payload(body: bytes) -> dict:
    """Returns headers to attach to outgoing ERP360 calls.
    `X-Signature` is HMAC-SHA256 of the raw body using the shared secret.
    Receiver (ERP360) verifies the same way it verifies our inbound calls."""
    import hashlib
    import hmac
    from datetime import datetime, timezone

    from core.config import settings

    secret = settings.erp360_sso_shared_secret
    if not secret:
        return {}
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    sig = hmac.new(secret.encode(), body + ts.encode(), hashlib.sha256).hexdigest()
    return {"X-Signature": sig, "X-Timestamp": ts, "X-Service-Token": secret}


from . import (  # noqa: E402, F401
    _academies_routes,
    _comments_routes,
    _portal_routes,
    _preview_routes,
    _uploads_routes,
)

