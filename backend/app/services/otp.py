"""Optional phone verification with a one-time code (OTP).

OTP_PROVIDER=off      PIN only (default).
OTP_PROVIDER=console  Demo: the code is written to the server log instead of being sent by SMS.
                      This shows the full verification flow without an SMS account. Never use
                      it on a public server.

To send real SMS, add a provider branch in `send_code` that calls your SMS gateway with an
API key read from backend/.env. Codes are stored only as salted hashes and expire.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from .. import config
from ..models import OtpChallenge
from ..timeutil import now_utc

log = logging.getLogger("kisansaathi.otp")
TOKEN_TTL_SECONDS = 30 * 60
MAX_CODE_ATTEMPTS = 5
_SECRET = (config.SECRET_KEY or secrets.token_hex(32)).encode("utf-8")


def otp_required() -> bool:
    return config.OTP_PROVIDER in {"console"}


def _code_hash(phone: str, code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}|{phone}|{code}".encode("utf-8") + _SECRET).hexdigest()


def send_code(db: Session, phone: str) -> dict:
    """Create a 6-digit code for this phone and deliver it with the configured provider."""
    if not otp_required():
        raise RuntimeError("Phone verification is not enabled on this server.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(8)
    db.query(OtpChallenge).filter(OtpChallenge.phone == phone).delete(synchronize_session=False)
    db.add(OtpChallenge(phone=phone, salt=salt, code_hash=_code_hash(phone, code, salt),
                        expires_at=now_utc() + timedelta(seconds=config.OTP_TTL_SECONDS), attempts=0))
    db.commit()
    if config.OTP_PROVIDER == "console":
        # Demo delivery only. A real gateway must never log the code.
        log.warning("DEMO OTP for %s******%s: %s (valid %s minutes)", phone[:2], phone[-2:], code,
                    config.OTP_TTL_SECONDS // 60)
    return {"sent": True, "expires_in": config.OTP_TTL_SECONDS, "provider": config.OTP_PROVIDER}


def verify_code(db: Session, phone: str, code: str) -> str | None:
    """Return a short-lived phone token if the code is right, otherwise None."""
    row = db.query(OtpChallenge).filter(OtpChallenge.phone == phone).one_or_none()
    if row is None:
        return None
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=now_utc().tzinfo)
    if expires < now_utc() or row.attempts >= MAX_CODE_ATTEMPTS:
        db.delete(row)
        db.commit()
        return None
    if not hmac.compare_digest(row.code_hash, _code_hash(phone, (code or "").strip(), row.salt)):
        row.attempts += 1
        db.commit()
        return None
    db.delete(row)
    db.commit()
    return issue_token(phone)


def issue_token(phone: str, ttl: int = TOKEN_TTL_SECONDS) -> str:
    expires = int(now_utc().timestamp()) + ttl
    signature = hmac.new(_SECRET, f"{phone}|{expires}".encode("utf-8"), hashlib.sha256).digest()
    return f"{expires}.{base64.urlsafe_b64encode(signature).decode('ascii').rstrip('=')}"


def token_valid(phone: str, token: str | None) -> bool:
    if not token or "." not in token:
        return False
    expires_text, _, signature = token.partition(".")
    try:
        expires = int(expires_text)
    except ValueError:
        return False
    if expires < int(now_utc().timestamp()):
        return False
    expected = base64.urlsafe_b64encode(
        hmac.new(_SECRET, f"{phone}|{expires}".encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    return hmac.compare_digest(expected, signature)
