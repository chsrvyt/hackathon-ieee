"""Application settings, loaded from environment variables.

Every tunable number used by the analytics engine lives here so thresholds are
never scattered through the code as magic numbers.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEV_SECRET = "dev-only-insecure-secret-key-change-me-0123456789"  # noqa: S105 - rejected in production


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- runtime -----------------------------------------------------------
    app_env: str = Field(default="development", description="development | test | production")
    log_level: str = "INFO"
    enable_docs: bool | None = None  # defaults to True outside production

    # --- database ----------------------------------------------------------
    database_url: str = "postgresql+psycopg://attendai:attendai@localhost:5432/attendai"

    # --- security ----------------------------------------------------------
    secret_key: str = _INSECURE_DEV_SECRET
    session_ttl_hours: int = 12
    session_cookie_name: str = "attendai_session"
    cookie_secure: bool | None = None  # defaults to True in production
    cookie_samesite: str = "lax"
    cors_origins: str = ""  # comma separated list of allowed origins
    frontend_origin: str = ""  # convenience alias, merged into cors_origins
    # WebView origins of the AttendAI mobile app (Capacitor: Android https://localhost, iOS capacitor://localhost).
    # The app authenticates with a bearer token, never cookies. Set to "" to disable the app.
    mobile_app_origins: str = "https://localhost,capacitor://localhost"
    login_max_failures: int = 8
    login_window_minutes: int = 15

    # --- uploads -----------------------------------------------------------
    max_upload_mb: float = 5.0
    max_upload_rows: int = 20000
    max_xlsx_uncompressed_mb: float = 60.0

    # --- analytics policy ----------------------------------------------------
    target_percentage: Decimal = Decimal("75")
    warning_band_points: Decimal = Decimal("5")
    trend_recent_periods: int = 2
    trend_threshold_points: Decimal = Decimal("5")
    default_planned_classes: int = 60

    # --- demo / static -----------------------------------------------------
    seed_demo_data: bool = False
    demo_mode: bool = False
    demo_password: str = "Demo@2026"  # noqa: S105 - public demo credential, override via DEMO_PASSWORD
    static_dir: str = ""  # path to the built frontend (served by FastAPI when set)

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, value: str) -> str:
        # Hosting providers hand out postgres:// or postgresql:// URLs; SQLAlchemy
        # needs the explicit psycopg (v3) driver name.
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @field_validator("cookie_samesite")
    @classmethod
    def _check_samesite(cls, value: str) -> str:
        value = value.lower()
        if value not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be lax, strict or none")
        return value

    @model_validator(mode="after")
    def _check_production(self) -> Settings:
        if self.is_production:
            if self.secret_key == _INSECURE_DEV_SECRET or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be set to a random value of at least 32 characters in production")
        if not (Decimal("0") < self.target_percentage <= Decimal("100")):
            raise ValueError("TARGET_PERCENTAGE must be in (0, 100]")
        if self.trend_recent_periods < 1:
            raise ValueError("TREND_RECENT_PERIODS must be >= 1")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def docs_enabled(self) -> bool:
        return (not self.is_production) if self.enable_docs is None else self.enable_docs

    @property
    def secure_cookies(self) -> bool:
        return self.is_production if self.cookie_secure is None else self.cookie_secure

    @property
    def allowed_origins(self) -> list[str]:
        raw = [*self.cors_origins.split(","), self.frontend_origin, *self.mobile_app_origins.split(",")]
        origins = []
        for item in raw:
            item = item.strip().rstrip("/")
            if item and item != "*" and item not in origins:
                origins.append(item)
        return origins

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    @property
    def static_path(self) -> Path | None:
        if not self.static_dir:
            return None
        path = Path(self.static_dir)
        return path if (path / "index.html").is_file() else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
