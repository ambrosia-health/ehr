from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Neon is preferred; SQLite keeps local development zero-config."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Ambrosia Health Domain API"
    environment: str = Field(
        default="development", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT")
    )
    database_url: str = Field(
        default="sqlite+aiosqlite:///./.ambrosia/ambrosia.db",
        validation_alias=AliasChoices("DATABASE_URL", "NEON_DATABASE_URL"),
    )
    session_secret: str = Field(
        default="local-demo-secret-change-before-deploy",
        validation_alias=AliasChoices(
            "AUTH_SESSION_SECRET", "SESSION_SECRET", "AMBROSIA_SESSION_SECRET"
        ),
    )
    session_cookie_name: str = "ambrosia_session"
    session_ttl_seconds: int = 60 * 60 * 12
    presenter_key: str = Field(
        default="ambrosia-demo",
        validation_alias=AliasChoices("DEMO_PRESENTER_SECRET", "PRESENTER_KEY"),
    )
    demo_mode: bool = True
    secure_cookies: bool = Field(
        default=False,
        validation_alias=AliasChoices("SESSION_COOKIE_SECURE", "SECURE_COOKIES"),
    )
    allow_demo_reset: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALLOW_SYNTHETIC_DEMO_RESET", "ALLOW_DEMO_RESET"),
    )
    auto_create_schema: bool = True
    auto_seed: bool = True
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    execution_platform: str = Field(default="local", validation_alias="EXECUTION_PLATFORM")
    ai_timeout_seconds: float = Field(
        default=8.0,
        validation_alias=AliasChoices("AI_REQUEST_TIMEOUT_SECONDS", "AI_TIMEOUT_SECONDS"),
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        value = str(value)
        if value.startswith("postgres://"):
            value = "postgresql://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://") and "+asyncpg" not in value:
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if not value.startswith("postgresql+asyncpg://"):
            return value
        # asyncpg accepts `ssl` but not libpq's `sslmode`/`channel_binding` keywords.
        parts = urlsplit(value)
        normalized_query = [
            ("ssl" if key == "sslmode" else key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key != "channel_binding"
        ]
        value = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(normalized_query), parts.fragment)
        )
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            if value.lstrip().startswith("["):
                return json.loads(value)
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def reject_insecure_production_defaults(self) -> Settings:
        if self.environment.lower() in {"production", "prod", "staging", "stage"}:
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise ValueError("Deployed DATABASE_URL must use PostgreSQL/Neon")
            if self.session_secret == "local-demo-secret-change-before-deploy":
                raise ValueError("AUTH_SESSION_SECRET must be set when deployed")
            if self.presenter_key == "ambrosia-demo":
                raise ValueError("DEMO_PRESENTER_SECRET must be set when deployed")
            if not self.secure_cookies:
                raise ValueError("SESSION_COOKIE_SECURE must be true when deployed")
            if self.session_cookie_name == "ambrosia_session":
                self.session_cookie_name = "__Host-ambrosia_session"
            self.auto_create_schema = False
            self.auto_seed = False
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
