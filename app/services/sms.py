"""
SMS notifications.

Providers:
- MockSMS   — logs (masked) instead of sending. Status "mocked".
- TwilioSMS — Twilio REST API over httpx with basic auth (no SDK). Status "sent".

`send_token_sms()` never raises: any failure is logged and reported as "failed".
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger("kiosk.sms")

TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def normalize_phone_in(phone: Optional[str]) -> Optional[str]:
    """Normalise an Indian mobile number to E.164 `+91XXXXXXXXXX`, or None if invalid."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    elif len(digits) == 13 and digits.startswith("091"):
        digits = digits[3:]
    if len(digits) != 10 or digits[0] not in "6789":
        return None
    return "+91" + digits


def mask_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 4:
        return "*" * len(digits)
    tail = digits[-4:]
    return "*" * (min(len(digits), 10) - 4) + tail


class SMSProvider(Protocol):
    name: str

    def send(self, to_e164: str, body: str) -> str:
        """Send a message. Returns an sms_status value ("sent" | "mocked"). May raise."""
        ...


class MockSMS:
    name = "mock"

    def send(self, to_e164: str, body: str) -> str:
        logger.info("[SMS:mock] to=%s chars=%d", mask_phone(to_e164), len(body))
        logger.debug("[SMS:mock] body=%s", body)
        return "mocked"


class TwilioSMS:
    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, from_number: str, timeout: float = 10.0):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.timeout = timeout

    def send(self, to_e164: str, body: str) -> str:
        if not (self.account_sid and self.auth_token and self.from_number):
            raise RuntimeError("Twilio credentials not configured")
        resp = httpx.post(
            TWILIO_API.format(sid=self.account_sid),
            data={"To": to_e164, "From": self.from_number, "Body": body},
            auth=(self.account_sid, self.auth_token),
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Twilio HTTP {resp.status_code}: {resp.text[:200]}")
        logger.info("[SMS:twilio] sent to=%s sid=%s", mask_phone(to_e164), resp.json().get("sid"))
        return "sent"


def get_provider() -> SMSProvider:
    if settings.SMS_PROVIDER == "twilio":
        return TwilioSMS(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_FROM_NUMBER)
    return MockSMS()


def token_sms_text(token: str, room: str, dept_name: str, wait_mins: int) -> str:
    return (
        f"{settings.HOSPITAL_NAME}: Your token is {token}. "
        f"Please go to {room} ({dept_name}). Approx wait {wait_mins} min."
    )


def send_token_sms(phone: Optional[str], token: str, room: str, dept_name: str, wait_mins: int) -> str:
    """Send the booking SMS. Returns sms_status; never raises."""
    to = normalize_phone_in(phone)
    if not to:
        logger.warning("[SMS] Opt-in but no valid phone number for token %s", token)
        return "failed"
    try:
        return get_provider().send(to, token_sms_text(token, room, dept_name, wait_mins))
    except Exception as e:  # never break booking
        logger.error("[SMS] Send failed for token %s: %s", token, e)
        return "failed"
