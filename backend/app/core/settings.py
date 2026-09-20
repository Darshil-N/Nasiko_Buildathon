"""Application settings, read from the environment (never from code or committed files)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_VERSION = "v1"
APP_VERSION = "0.1.0"
_PLACEHOLDER_KEYS = frozenset({"change-me", "changeme", "secret", "password"})


class Settings(BaseSettings):
    """Backend configuration. Variable names match ``.env.example``."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["dev", "prod"] = "dev"
    database_url: str
    backend_api_key: SecretStr = Field(min_length=8)
    allowed_origins: str = "http://localhost:8501"  # comma-separated
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    nasiko_base_url: str = "http://localhost:8080"

    @model_validator(mode="after")
    def _reject_placeholder_key_in_prod(self) -> Settings:
        key = self.backend_api_key.get_secret_value().strip().lower()
        if self.environment == "prod" and key in _PLACEHOLDER_KEYS:
            raise ValueError("BACKEND_API_KEY is a placeholder; set a real secret in production")
        return self

    @property
    def cors_origins(self) -> list[str]:
        """``allowed_origins`` split into a clean list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""
    return Settings()  # required fields come from the environment
