"""
Application settings — single place where environment variables are read.

Values come from the process environment and from `<project root>/.env`.
See `.env.example` for every option.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DEFAULT_JWT_SECRET = "dev-insecure-secret"

logger = logging.getLogger("kiosk.config")


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    ENV: Literal["dev", "prod"] = "dev"
    DATABASE_URL: str = "sqlite:///./patients.db"

    # Groq (cloud STT + LLM)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_TRIAGE_MODEL: str = "openai/gpt-oss-120b"
    GROQ_WHISPER_MODEL: str = "whisper-large-v3-turbo"
    GROQ_TIMEOUT: float = 30.0
    GROQ_WHISPER_TIMEOUT: float = 30.0

    # Speech providers (see docs/CONTRACT.md "Speech providers")
    # Sarvam docs: https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe
    #              https://docs.sarvam.ai/api-reference-docs/text-to-speech/convert
    STT_PROVIDER: Literal["groq", "sarvam"] = "groq"
    TTS_PROVIDER: Literal["browser", "sarvam"] = "browser"
    SARVAM_API_KEY: str = ""
    SARVAM_STT_MODEL: str = "saaras:v4"
    SARVAM_TTS_MODEL: str = "bulbul:v3"
    SARVAM_TTS_SPEAKER_TA: str = "kavitha"
    SARVAM_TTS_SPEAKER_EN: str = "priya"
    SARVAM_TIMEOUT: float = 30.0
    # The REST STT endpoint is meant for short clips (docs give no hard cap);
    # larger uploads go to Groq or are rejected.
    SARVAM_STT_MAX_BYTES: int = 2_000_000
    TTS_RATE_LIMIT_PER_MIN: int = 60
    TTS_CACHE_SIZE: int = 256

    # Auth
    JWT_SECRET: str = DEFAULT_JWT_SECRET
    JWT_EXPIRE_MINUTES: int = 720
    KIOSK_DEVICE_KEYS: str = ""          # comma list
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174"  # comma list

    # Face recognition
    FACE_MATCH_THRESHOLD: float = 0.45
    FACE_GALLERY_SIZE: int = 5
    # A match only adds the new photo to the patient's gallery when it is this close
    # (cosine distance). Borderline matches never teach the gallery a wrong face.
    FACE_GALLERY_UPDATE_MAX_DIST: float = 0.30
    # If a second patient is within this distance of the best match (and also under
    # the threshold), the scan is ambiguous and the kiosk falls back to phone check-in.
    FACE_AMBIGUITY_MARGIN: float = 0.08
    # Reject faces that look like a printed photo or a phone/tablet screen (MiniFASNet).
    FACE_ANTI_SPOOFING: bool = True
    # Load (and on first run download) face models in the background at server start.
    FACE_WARMUP: bool = True

    # SMS
    SMS_PROVIDER: Literal["mock", "twilio"] = "mock"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    HOSPITAL_NAME: str = "City Hospital"

    # Phone OTP identification (face opt-out)
    OTP_TTL_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RATE_LIMIT: int = 3              # codes per phone per OTP_RATE_WINDOW_MINUTES
    OTP_RATE_WINDOW_MINUTES: int = 10
    # Lifetime of the signed proof returned by /identify/phone/verify and required by
    # /register when no face template is enrolled.
    PHONE_VERIFICATION_TOKEN_MINUTES: int = 15

    # Version label stored with each face consent (bump when the consent text changes).
    CONSENT_VERSION: str = "v1-2026-11"

    # Clinical rules: age (years) below which a patient is treated as a child.
    CHILD_AGE_YEARS: int = 14

    SEED_DEMO_USERS: bool = True

    @property
    def sarvam_configured(self) -> bool:
        k = self.SARVAM_API_KEY.strip()
        return bool(k) and not k.startswith("REPLACE_ME")

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def is_prod(self) -> bool:
        return self.ENV == "prod"

    @property
    def kiosk_keys(self) -> list[str]:
        return _split_csv(self.KIOSK_DEVICE_KEYS)

    @property
    def cors_origins(self) -> list[str]:
        return _split_csv(self.CORS_ORIGINS)

    @property
    def database_url(self) -> str:
        """DATABASE_URL with relative SQLite paths resolved against the project root."""
        url = self.DATABASE_URL
        prefix = "sqlite:///"
        if url.startswith(prefix) and not url.startswith("sqlite:////"):
            path = url[len(prefix):]
            if path and path != ":memory:" and not Path(path).is_absolute():
                return prefix + (BASE_DIR / path).resolve().as_posix()
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    def validate_for_startup(self) -> None:
        """Fail fast on unsafe production configuration."""
        errors: list[str] = []
        if self.is_prod:
            if not self.JWT_SECRET or self.JWT_SECRET == DEFAULT_JWT_SECRET:
                errors.append("JWT_SECRET must be set to a strong random value when ENV=prod")
            if not self.kiosk_keys:
                errors.append("KIOSK_DEVICE_KEYS must list at least one kiosk key when ENV=prod")
            if "*" in self.cors_origins:
                errors.append("CORS_ORIGINS must not contain '*' when ENV=prod")
        if self.SMS_PROVIDER == "twilio" and not (
            self.TWILIO_ACCOUNT_SID and self.TWILIO_AUTH_TOKEN and self.TWILIO_FROM_NUMBER
        ):
            msg = "SMS_PROVIDER=twilio requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER"
            if self.is_prod:
                errors.append(msg)
            else:
                logger.warning("[Config] %s — SMS will fail", msg)
        if errors:
            raise RuntimeError("Invalid configuration:\n  - " + "\n  - ".join(errors))
        if not self.is_prod:
            if self.JWT_SECRET == DEFAULT_JWT_SECRET:
                logger.warning("[Config] Using the default dev JWT_SECRET (ENV=dev)")
            if not self.kiosk_keys:
                logger.warning("[Config] KIOSK_DEVICE_KEYS empty — kiosk key check disabled (ENV=dev)")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
