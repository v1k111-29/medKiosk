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
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_TRIAGE_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_WHISPER_MODEL: str = "whisper-large-v3-turbo"
    GROQ_TIMEOUT: float = 30.0
    GROQ_WHISPER_TIMEOUT: float = 30.0

    # Auth
    JWT_SECRET: str = DEFAULT_JWT_SECRET
    JWT_EXPIRE_MINUTES: int = 720
    KIOSK_DEVICE_KEYS: str = ""          # comma list
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174"  # comma list

    # Face recognition
    FACE_MATCH_THRESHOLD: float = 0.45
    FACE_GALLERY_SIZE: int = 5

    # SMS
    SMS_PROVIDER: Literal["mock", "twilio"] = "mock"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    HOSPITAL_NAME: str = "City Hospital"

    SEED_DEMO_USERS: bool = True

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
