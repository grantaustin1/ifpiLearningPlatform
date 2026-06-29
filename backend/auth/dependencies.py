"""FastAPI auth dependencies — mirrors ERP360's `auth/dependencies.py` shape."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth.cookies import COOKIE_NAME
from core.database import get_db
from core.role_registry import normalize_role_names
from core.security import decode_token
from models.user import User

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def extract_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """Authorization header takes priority, then HTTP-only cookie."""
    if credentials and credentials.credentials:
        return credentials.credentials
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        return cookie_token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


class CurrentUser(BaseModel):
    """Authenticated principal — passed into all protected routes."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: Optional[str] = None
    organization_id: int
    roles: List[str] = []

    def has_any_role(self, allowed: List[str] | set[str] | frozenset[str]) -> bool:
        return any(r in allowed for r in self.roles)


def get_current_user(
    token: str = Depends(extract_token),
    db: Session = Depends(get_db),
) -> CurrentUser:
    # Iter 21 — API token path. Tokens are prefixed `ifpi_` so we can route
    # them past the JWT decoder without paying its CPU cost.
    if token.startswith("ifpi_"):
        from auth.api_tokens import authenticate_api_token
        principal = authenticate_api_token(db, token)
        if not principal:
            raise HTTPException(status_code=401, detail="Invalid API token")
        return principal

    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Wrong token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or not found")

    roles = normalize_role_names([ur.role for ur in user.user_roles])
    if not roles:
        roles = ["LEARNER"]

    return CurrentUser(
        id=user.id,
        email=user.email,
        name=user.name,
        organization_id=user.organization_id,
        roles=roles,
    )


def requires_roles(*allowed: str):
    """Decorator-dependency that enforces role membership."""
    allowed_set = set(normalize_role_names(allowed))

    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current_user.has_any_role(allowed_set):
            raise HTTPException(status_code=403, detail="Insufficient role")
        return current_user

    return _check
