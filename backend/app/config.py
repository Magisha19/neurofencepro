"""NeuroFence settings (environment variables with prefix NEUROFENCE_)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"
DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEUROFENCE_", env_file=".env", extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./data/neurofence.db"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_minutes: int = Field(60, ge=5, le=1440)
    bcrypt_rounds: int = Field(12, ge=4, le=15)

    cors_origins: list[str] = ["http://localhost:5173"]

    login_max_failures: int = Field(5, ge=1, le=50)
    login_window_seconds: int = Field(300, ge=10, le=3600)
    runner_enabled: bool = True
    runner_workers: int = Field(1, ge=1, le=4)
    stub_stage_delay_seconds: float = Field(0.0, ge=0, le=5)  # dev only: slows the stub stages

    @model_validator(mode="after")
    def _production_needs_real_secret(self) -> "Settings":
        if self.env == "production" and (
            self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError("production requires NEUROFENCE_JWT_SECRET (at least 32 chars)")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()