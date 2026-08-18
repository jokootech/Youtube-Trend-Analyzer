"""
Configuration management using Pydantic v2 Settings.

All application configuration is loaded from environment variables
or the .env file at the project root. This module provides a
centrally validated, typed settings object consumed by all
other modules in the project.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LLMProvider(str, Enum):
    """Supported LLM backends."""

    GEMINI = "gemini"
    OPENAI = "openai"


class LogLevel(str, Enum):
    """Log levels recognised by Loguru."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RunMode(str, Enum):
    """Execution mode."""

    ONCE = "once"
    SCHEDULED = "scheduled"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """Application settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Application ---------------------------------------------------------

    app_name: str = Field(
        default="YouTube Trend Analyzer",
        description="Bot display name",
    )

    run_mode: RunMode = Field(
        default=RunMode.SCHEDULED,
        description="once | scheduled",
    )

    poll_interval_minutes: int = Field(
        default=60,
        ge=5,
        description="Minutes between scheduled runs (minimum 5)",
    )

    log_level: LogLevel = Field(
        default=LogLevel.INFO,
    )

    # -- Proxy ---------------------------------------------------------------

    # Empty on GitHub Actions. This prevents the code from falling back
    # to the developer's local SOCKS proxy.
    http_proxy: str = Field(
        default="",
        description="Optional HTTP/SOCKS proxy URL",
    )

    # -- YouTube API & Token Constraints -------------------------------------

    youtube_api_key: SecretStr = Field(
        ...,
        description="YouTube Data API v3 key",
    )

    youtube_rss_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="RSS fetch timeout in seconds",
    )

    youtube_api_timeout: int = Field(
        default=15,
        ge=3,
        le=60,
        description="API request timeout in seconds",
    )

    youtube_max_results: int = Field(
        default=50,
        ge=1,
        le=50,
        description="Max videos per RSS/API call",
    )

    youtube_max_comments: int = Field(
        default=10,
        ge=3,
        le=30,
        description="Top comments to fetch per video",
    )

    video_age_days_max: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Max video age in days",
    )

    top_n_videos: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Top-N videos by velocity to process",
    )

    # -- LLM Engine ----------------------------------------------------------

    llm_provider: LLMProvider = Field(
        default=LLMProvider.GEMINI,
    )

    gemini_api_key: SecretStr = Field(
        ...,
        validation_alias="gemini_api_keys",
        description="Gemini API Key",
    )

    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model identifier",
    )

    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai",
        description="Gemini OpenAI-compatible API base URL",
    )

    openai_api_key: SecretStr | None = Field(
        default=None,
    )

    openai_model: str = Field(
        default="gpt-4o",
    )

    llm_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
    )

    llm_max_tokens: int = Field(
        default=1200,
        ge=256,
        le=4096,
    )

    llm_request_timeout: int = Field(
        default=60,
        ge=5,
        le=300,
    )

    # -- Telegram Notifier ---------------------------------------------------

    telegram_bot_token: SecretStr = Field(
        ...,
        description="Telegram Bot API token",
    )

    telegram_chat_id: str = Field(
        ...,
        description="Target chat (or channel) ID",
    )

    telegram_parse_mode: Literal["HTML", "Markdown"] = Field(
        default="HTML",
    )

    telegram_disable_web_preview: bool = Field(
        default=True,
    )

    telegram_send_timeout: int = Field(
        default=15,
        ge=3,
        le=60,
    )

    # -- Database ------------------------------------------------------------

    db_path: Path = Field(
        default=PROJECT_ROOT / "data" / "trends.db",
        description="Path to the SQLite database file",
    )

    # -- Topic / Channel inputs ----------------------------------------------

    target_topics: list[str] = Field(
        default_factory=lambda: [
            "technology",
            "AI",
            "startup",
        ],
        description="List of search topics to monitor",
    )

    target_channel_ids: list[str] = Field(
        default_factory=list,
        description="YouTube channel IDs to monitor directly",
    )

    # -----------------------------------------------------------------------
    # Validators
    # -----------------------------------------------------------------------

    @field_validator("gemini_api_key")
    @classmethod
    def _require_gemini_key(
        cls,
        v: SecretStr | None,
        info,
    ) -> SecretStr | None:
        if info.data.get("llm_provider") == LLMProvider.GEMINI and v is None:
            raise ValueError(
                "gemini_api_key is required when llm_provider=gemini"
            )
        return v

    @field_validator("openai_api_key")
    @classmethod
    def _require_openai_key(
        cls,
        v: SecretStr | None,
        info,
    ) -> SecretStr | None:
        if info.data.get("llm_provider") == LLMProvider.OPENAI and v is None:
            raise ValueError(
                "openai_api_key is required when llm_provider=openai"
            )
        return v

    # -----------------------------------------------------------------------
    # Derived helpers
    # -----------------------------------------------------------------------

    @property
    def active_llm_api_key(self) -> SecretStr:
        """Return the API secret for the currently selected LLM provider."""

        if self.llm_provider == LLMProvider.GEMINI and self.gemini_api_key:
            return self.gemini_api_key

        if self.openai_api_key:
            return self.openai_api_key

        raise ValueError("No valid LLM API key configured.")

    @property
    def active_llm_model(self) -> str:
        """Return the model identifier for the active provider."""

        if self.llm_provider == LLMProvider.GEMINI:
            return self.gemini_model

        return self.openai_model


# ---------------------------------------------------------------------------
# Cached singleton
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    return Settings()
