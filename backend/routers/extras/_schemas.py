from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LeadIn(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    source: Optional[str] = "embed"
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    country: Optional[str] = None
    organization_slug: Optional[str] = None    # which academy to attribute to


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    description: Optional[str] = None
    cert_accent_color: Optional[str] = None
    cert_signature_text: Optional[str] = None
    cert_signature_image_url: Optional[str] = None
    cert_footer_text: Optional[str] = None
    marketplace_opt_in: Optional[bool] = None


class CohortSettingsIn(BaseModel):
    cohort_threshold: int = Field(ge=1, le=100, default=75)
    cohort_celebration_webhook_url: Optional[str] = None
    cohort_digest_enabled: Optional[bool] = None  # None = leave unchanged


class WebhookTestIn(BaseModel):
    webhook_url: str = Field(min_length=8, max_length=500)


class SmtpConfigIn(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None  # plain in transit, encrypted at rest
    smtp_from_email: Optional[str] = None
    smtp_from_name: Optional[str] = None
    smtp_use_tls: bool = True
