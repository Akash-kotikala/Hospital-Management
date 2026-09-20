import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Project metadata
    PROJECT_NAME: str = "Autonomous Healthcare Intake & Scheduling Platform"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./healthcare_platform.db",
        description="Async database connection string. Use postgresql+asyncpg://... for PostgreSQL."
    )

    # Security & JWT
    JWT_SECRET_KEY: str = Field(
        default="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
        description="Secret key for signing JWT tokens"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # AI & Gemini API
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API key")
    GEMINI_MODEL: str = "gemini-2.5-flash"
    AI_DEMO_MODE: bool = False  # Auto-falls back to deterministic simulation if key missing

    # Redis (Optional / background workers)
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"

    # Notification & Mail
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "notifications@healthcareplatform.local"
    SMTP_PASSWORD: str = "mock-password"
    EMAILS_FROM_EMAIL: str = "no-reply@healthcareplatform.local"

    # Mock EHR Connector
    EHR_BASE_URL: str = "http://localhost:8000/mock-ehr"
    EHR_API_KEY: str = "mock-ehr-secret-key"
    EHR_TIMEOUT_SECONDS: float = 3.0

    # Observability
    CORRELATION_ID_HEADER: str = "X-Correlation-ID"
    OPERATION_ID_HEADER: str = "X-Operation-ID"


settings = Settings()
