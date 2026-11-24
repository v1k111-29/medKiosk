"""
Phone one-time-code identification for patients who decline face recognition.

- 6-digit numeric code, stored only as an HMAC-SHA256 (keyed with JWT_SECRET, bound to the phone).
- Expires after OTP_TTL; at most OTP_MAX_ATTEMPTS wrong guesses per code.
- `start` is rate-limited per phone (OTP_RATE_LIMIT codes per OTP_RATE_WINDOW).
- Starting a new code invalidates earlier unused codes for the same phone.
- Old rows are purged on startup and (at most once a minute) when a code is started.
  Rows are kept for max(OTP_TTL, OTP_RATE_WINDOW) so purging never weakens the rate limit.

Limits come from settings (OTP_TTL_MINUTES, OTP_MAX_ATTEMPTS, OTP_RATE_LIMIT,
OTP_RATE_WINDOW_MINUTES).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import PhoneOtp, utcnow

logger = logging.getLogger("kiosk.otp")

OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=settings.OTP_TTL_MINUTES)
OTP_MAX_ATTEMPTS = settings.OTP_MAX_ATTEMPTS
OTP_RATE_LIMIT = settings.OTP_RATE_LIMIT
OTP_RATE_WINDOW = timedelta(minutes=settings.OTP_RATE_WINDOW_MINUTES)

# Opportunistic purge on `start` runs at most this often (seconds, monotonic clock).
_PURGE_INTERVAL_S = 60.0
_last_purge: Optional[float] = None


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


def purge_expired(session: Session) -> int:
    """Delete OTP rows no longer needed for verification or rate limiting. Commits; returns rows deleted."""
    cutoff = utcnow() - max(OTP_TTL, OTP_RATE_WINDOW)
    result = session.execute(delete(PhoneOtp).where(PhoneOtp.created_at < cutoff))
    session.commit()
    return int(result.rowcount or 0)


def _maybe_purge(session: Session) -> None:
    global _last_purge
    now = time.monotonic()
    if _last_purge is not None and now - _last_purge < _PURGE_INTERVAL_S:
        return
    _last_purge = now
    try:
        deleted = purge_expired(session)
        if deleted:
            logger.info("[OTP] Purged %d old code(s)", deleted)
    except Exception as e:  # never block issuing a code on housekeeping
        session.rollback()
        logger.warning("[OTP] Purge failed: %s", e)


def start(session: Session, phone: str) -> str:
    """Create a new code for `phone` (E.164) and return it (caller sends it). Raises OtpRateLimited."""
    _maybe_purge(session)
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
