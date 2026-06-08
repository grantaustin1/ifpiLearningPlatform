"""Per-tenant SMTP override service.

Each organization can configure its own SMTP server. When `smtp_host` is
populated on the Organization row, the outbox worker dispatches via that
server instead of the global stub. Passwords are encrypted at rest using
Fernet (symmetric AES-128). The encryption key is held in the environment
as `SMTP_ENCRYPTION_KEY` (32 url-safe base64 bytes). When the key is
missing, encryption is a no-op pass-through — usable in dev, NEVER in prod.
"""
from __future__ import annotations

import base64
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("ifpi.smtp")


def _key() -> Optional[bytes]:
    raw = os.environ.get("SMTP_ENCRYPTION_KEY", "").strip()
    if not raw:
        return None
    # Allow either a properly-formed Fernet key or any 32 raw bytes the
    # operator passes — we derive a Fernet key from it.
    try:
        # Already valid base64 fernet key (44 chars ending in '=')
        Fernet(raw.encode())
        return raw.encode()
    except Exception:
        # Derive: pad/truncate to 32 bytes then urlsafe-b64
        padded = (raw.encode() + b"\0" * 32)[:32]
        return base64.urlsafe_b64encode(padded)


def encrypt_password(plaintext: str) -> str:
    if not plaintext:
        return ""
    key = _key()
    if not key:
        # In production we refuse to store plaintext. The env flag below
        # opts in to dev-mode plaintext storage for local development.
        if os.environ.get("SMTP_ALLOW_PLAINTEXT", "").lower() in ("1", "true", "yes"):
            logger.warning("SMTP_ENCRYPTION_KEY unset — storing SMTP password in plaintext (DEV ONLY).")
            return f"plain:{plaintext}"
        raise RuntimeError(
            "SMTP_ENCRYPTION_KEY env var is required to persist SMTP passwords. "
            "Set a 32-byte url-safe base64 key, or set SMTP_ALLOW_PLAINTEXT=1 for dev only."
        )
    return f"enc:{Fernet(key).encrypt(plaintext.encode()).decode()}"


def decrypt_password(stored: str) -> str:
    if not stored:
        return ""
    if stored.startswith("plain:"):
        return stored[6:]
    if stored.startswith("enc:"):
        key = _key()
        if not key:
            raise RuntimeError("SMTP_ENCRYPTION_KEY required to decrypt password")
        try:
            return Fernet(key).decrypt(stored[4:].encode()).decode()
        except InvalidToken:
            raise RuntimeError("SMTP password decryption failed — wrong SMTP_ENCRYPTION_KEY?")
    # Legacy/unknown — treat as plaintext
    return stored


def send_via_org_smtp(*, host: str, port: int, username: Optional[str],
                     password_enc: Optional[str], use_tls: bool,
                     from_email: str, from_name: Optional[str],
                     to_email: str, to_name: Optional[str],
                     subject: str, body_html: str, body_text: str = "",
                     timeout: int = 15) -> None:
    """Synchronously send one email via the org's SMTP server.

    Raises smtplib.SMTPException on any failure — caller (outbox worker)
    is responsible for marking the row FAILED / scheduling retry.
    """
    msg = MIMEMultipart("alternative")
    sender = f"{from_name} <{from_email}>" if from_name else from_email
    recipient = f"{to_name} <{to_email}>" if to_name else to_email
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    password = decrypt_password(password_enc or "")
    with smtplib.SMTP(host, port, timeout=timeout) as s:
        if use_tls:
            s.starttls()
        if username:
            s.login(username, password)
        s.sendmail(from_email, [to_email], msg.as_string())
    logger.info("SMTP delivered to %s via %s:%s", to_email, host, port)
