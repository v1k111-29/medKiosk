"""
Phone one-time-code identification for patients who decline face recognition.

- 6-digit numeric code, stored only as an HMAC-SHA256 (keyed with JWT_SECRET, bound to the phone).
- Expires after OTP_TTL; at most OTP_MAX_ATTEMPTS wrong guesses per code.
- `start` is rate-limited per phone (OTP_RATE_LIMIT codes per OTP_RATE_WINDOW).
- Starting a new code invalidates earlier unused codes for the same phone.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import PhoneOtp, utcnow

# TODO: move to settings (app/core/config.py) once config changes are allowed.
OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=5)
OTP_MAX_ATTEMPTS = 5
OTP_RATE_LIMIT = 3
OTP_RATE_WINDOW = timedelta(minutes=10)


class OtpRateLimited(Exception):
    pass


@dataclass
class VerifyResult:
    ok: bool
    reason: str = ""  # "invalid" | "expired" | "locked"
    attempts_left: int = 0


def generate_otp() -> str:
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def hash_otp(phone: str, otp: str) -> str:
    return hmac.new(settings.JWT_SECRET.encode(), f"otp:{phone}:{otp}".encode(), hashlib.sha256).hexdigest()


def start(session: Session, phone: str) -> str:
    """Create a new code for `phone` (E.164) and return it (caller sends it). Raises OtpRateLimited."""
    now = utcnow()
    recent = session.scalar(
        select(func.count()).select_from(PhoneOtp).where(
            PhoneOtp.phone == phone, PhoneOtp.created_at >= now - OTP_RATE_WINDOW
        )
    ) or 0
    if recent >= OTP_RATE_LIMIT:
        raise OtpRateLimited()

    session.execute(
        update(PhoneOtp)
        .where(PhoneOtp.phone == phone, PhoneOtp.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    otp = generate_otp()
    session.add(PhoneOtp(phone=phone, otp_hash=hash_otp(phone, otp), created_at=now, expires_at=now + OTP_TTL))
    session.commit()
    return otp


def verify(session: Session, phone: str, otp: str) -> VerifyResult:
    now = utcnow()
    row: Optional[PhoneOtp] = session.scalars(
        select(PhoneOtp)
        .where(PhoneOtp.phone == phone, PhoneOtp.consumed_at.is_(None))
        .order_by(PhoneOtp.created_at.desc(), PhoneOtp.id.desc())
        .limit(1)
    ).first()
    if row is None:
        return VerifyResult(False, "invalid")
    if row.expires_at <= now:
        row.consumed_at = now
        session.commit()
        return VerifyResult(False, "expired")
    if row.attempts >= OTP_MAX_ATTEMPTS:
        row.consumed_at = now
        session.commit()
        return VerifyResult(False, "locked")

    if hmac.compare_digest(row.otp_hash, hash_otp(phone, (otp or "").strip())):
        row.consumed_at = now
        session.commit()
        return VerifyResult(True)

    row.attempts += 1
    left = OTP_MAX_ATTEMPTS - row.attempts
    if left <= 0:
        row.consumed_at = now
    session.commit()
    return VerifyResult(False, "locked" if left <= 0 else "invalid", max(left, 0))
