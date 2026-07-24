from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class InvitationCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    role: str = "INSTRUCTOR"


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: Optional[str]
    role: str
    invited_by_id: Optional[int]
    accepted_at: Optional[datetime]
    revoked_at: Optional[datetime]
    expires_at: datetime
    created_at: datetime
    status: str


class BulkInviteRow(BaseModel):
    email: str
    name: Optional[str] = None
    role: str = "LEARNER"


class BulkInviteBody(BaseModel):
    invitations: List[BulkInviteRow]
    cohort: Optional[str] = None


class InvitationAccept(BaseModel):
    password: str
    name: Optional[str] = None


class InvitationLookup(BaseModel):
    email: str
    name: Optional[str]
    role: str
    organization_name: str
