from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class CertPreviewBody(BaseModel):
    organisation_name: Optional[str] = "Sample Academy"
    organisation_logo_url: Optional[str] = None
    accent_color: Optional[str] = "#6366f1"
    signature_text: Optional[str] = None
    signature_image_url: Optional[str] = None
    footer_text: Optional[str] = None


class CommentIn(BaseModel):
    body: str
    parent_id: Optional[int] = None


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slide_id: int
    user_id: int
    user_name: Optional[str]
    body: str
    parent_id: Optional[int]
    created_at: datetime


class AcademyCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    admin_email: EmailStr
    admin_name: Optional[str] = None
