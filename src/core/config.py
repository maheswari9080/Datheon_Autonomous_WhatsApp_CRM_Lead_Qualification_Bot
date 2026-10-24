"""Application configuration module using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production application settings with strict validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Datheon WhatsApp Sales Intelligence"
    APP_ENV: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ADMIN_API_KEY: str = Field(
        default="datheon-super-secure-admin-key-change-in-prod",
        description="Bearer token for protected admin endpoints",
    )

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./app.db",
        description="Async SQLAlchemy database connection URI",
    )
    DB_ECHO: bool = False

    # Meta WhatsApp Cloud API
    META_VERIFY_TOKEN: str = Field(
        default="datheon_whatsapp_verify_token_default",
        description="Verification token for GET webhook handshake",
    )
    META_APP_SECRET: str = Field(
        default="meta_app_secret_placeholder_for_hmac_sha256",
        description="App secret used to verify X-Hub-Signature-256",
    )
    META_PHONE_NUMBER_ID: str = Field(
        default="100000000000001",
        description="Meta business phone number ID",
    )
    META_ACCESS_TOKEN: str = Field(
        default="meta_access_token_placeholder",
        description="System user permanent access token for WhatsApp API",
    )
    META_API_VERSION: str = "v21.0"

    # AI & LLM Qualification
    LLM_PROVIDER: Literal["mock", "openai", "ollama"] = "mock"
    OPENAI_API_KEY: str = Field(
        default="sk-placeholder-openai-key",
        description="OpenAI API key (if provider is openai)",
    )
    OPENAI_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: float = 8.0
    MIN_QUALIFICATION_BUDGET: float = 1000.0  # USD
    QUALIFICATION_CONFIDENCE_THRESHOLD: float = 0.70

    # Calendar Integration
    CALENDAR_PROVIDER: Literal["google", "calcom", "mock"] = "mock"
    GOOGLE_CALENDAR_ID: str = "primary"
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    CALCOM_API_KEY: str = "calcom_api_key_placeholder"
    CALCOM_EVENT_TYPE_ID: int = 12345
    BUSINESS_HOURS_START: int = 9  # 9:00 AM
    BUSINESS_HOURS_END: int = 18  # 6:00 PM
    DEFAULT_TIMEZONE: str = "UTC"
    MEETING_DURATION_MINUTES: int = 30
    MIN_NOTICE_HOURS: int = 2

    # CRM Integration
    CRM_PROVIDER: Literal["airtable", "mock"] = "mock"
    AIRTABLE_API_KEY: str = "pat_placeholder_airtable"
    AIRTABLE_BASE_ID: str = "app_placeholder_base"
    AIRTABLE_TABLE_NAME: str = "Leads"

    # Human Escalation & Notifications
    SLACK_WEBHOOK_URL: str = Field(
        default="",
        description="Slack incoming webhook URL for escalation notifications",
    )

    # Security & Rate Limiting
    MAX_CONCURRENT_LOCK_SECONDS: int = 300
    MESSAGE_DEDUP_TTL_SECONDS: int = 86400  # 24 hours

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        # Normalize sqlite:// to sqlite+aiosqlite:// if needed
        if v.startswith("sqlite:///") and not v.startswith("sqlite+aiosqlite:///"):
            return v.replace("sqlite:///", "sqlite+aiosqlite:///")
        if v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
            return v.replace("postgresql://", "postgresql+asyncpg://")
        return v


@lru_cache
def get_settings() -> Settings:
    """Singleton cached application settings."""
    return Settings()
