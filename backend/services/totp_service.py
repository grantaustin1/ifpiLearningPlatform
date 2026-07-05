"""TOTP-based 2FA service (RFC 6238).

Small, self-contained wrapper around PyOTP + qrcode for time-based
one-time passwords. Secrets are stored Fernet-encrypted (reusing the
`SMTP_ENCRYPTION_KEY` pipeline). Recovery codes are hashed with bcrypt
before persistence so a stolen DB dump can't reveal them.

Design decisions
----------------
- 30-second time step, 6-digit code, SHA-1 (standard authenticator apps).
- Time-skew tolerance: ±1 window (default `pyotp.TOTP.verify(valid_window=1)`).
- Recovery codes: 10 codes at 8 base32 chars each (~40 bits). Bcrypt-hashed;
  single-use — verify + consume in the same call.
- Provisioning URI uses the org name as issuer so users see
  "IFPI Learning · admin@ifpi.org" in their authenticator app.
"""
from __future__ import annotations

import base64
import io
import secrets
from typing import Optional

import bcrypt
import pyotp
import qrcode

from services.smtp_service import decrypt_password, encrypt_password


# ── Secret + recovery code generation ──────────────────────────────────


def generate_secret() -> str:
    """32-char base32 secret suitable for RFC 6238 TOTP."""
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    """Fernet-encrypt the secret using the shared SMTP key pipeline."""
    return encrypt_password(secret)


def decrypt_secret(enc: str) -> str:
    return decrypt_password(enc)


def generate_recovery_codes(count: int = 10) -> list[str]:
    """Return `count` human-friendly recovery codes (8 base32 chars each,
    grouped as XXXX-XXXX). Caller must show these ONCE and store only
    the bcrypt hashes."""
    codes = []
    for _ in range(count):
        raw = base64.b32encode(secrets.token_bytes(5)).decode().rstrip("=")
        code = f"{raw[:4]}-{raw[4:8]}"
        codes.append(code)
    return codes


def hash_recovery_codes(codes: list[str]) -> list[str]:
    return [
        bcrypt.hashpw(c.upper().replace("-", "").encode(), bcrypt.gensalt(rounds=10)).decode()
        for c in codes
    ]


def verify_recovery_code(code: str, hashed_codes: list[str]) -> Optional[int]:
    """Return the index of the matched hash so the caller can invalidate
    it (single-use). Returns None if no match."""
    normalized = code.upper().replace("-", "").replace(" ", "").encode()
    for i, h in enumerate(hashed_codes or []):
        if not h:
            continue
        try:
            if bcrypt.checkpw(normalized, h.encode()):
                return i
        except (ValueError, TypeError):
            continue
    return None


# ── TOTP verification + provisioning ───────────────────────────────────


def verify_code(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code with ±30s clock-skew tolerance."""
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def provisioning_uri(secret: str, account_name: str,
                     issuer: str = "IFPI Learning") -> str:
    """otpauth:// URI compatible with Google Authenticator / Authy / 1Password."""
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)


def qr_svg(uri: str) -> str:
    """Render the provisioning URI as an inline SVG (returned as string,
    ready to embed in a data URL or dropped straight into the DOM)."""
    from qrcode.image.svg import SvgImage
    img = qrcode.make(uri, image_factory=SvgImage, box_size=10)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


def qr_png_base64(uri: str) -> str:
    """Render the provisioning URI as base64 PNG, wrapped as a data URL."""
    img = qrcode.make(uri, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
