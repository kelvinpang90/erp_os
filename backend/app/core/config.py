from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "ERP OS"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    DEBUG: bool = False
    DEMO_MODE: bool = False

    # ── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:80"

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str  # e.g. mysql+aiomysql://user:pass@host:3306/dbname
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # DB assignments
    REDIS_DB_DEFAULT: int = 0   # general / Celery broker
    REDIS_DB_CACHE: int = 1     # dashboard / hot data cache
    REDIS_DB_AUTH: int = 2      # refresh tokens
    REDIS_DB_RATE: int = 3      # rate limit counters

    # ── AI ────────────────────────────────────────────────────────────────────
    AI_ENABLED: bool = True
    ANTHROPIC_API_KEY: str = ""
    AI_TIMEOUT_SECONDS: int = 3

    # OCR — Claude Vision based PO invoice extraction
    AI_OCR_MODEL: str = "claude-sonnet-4-6"
    AI_OCR_TIMEOUT_SECONDS: int = 30
    AI_OCR_DAILY_QUOTA: int = 20
    AI_OCR_MAX_FILE_MB: int = 10

    # ── File Storage ──────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_MB: int = 20

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = ""   # defaults built in redis.py
    CELERY_RESULT_BACKEND: str = ""

    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""

    # ── Inventory / Goods Receipt ────────────────────────────────────────────
    # Allowed over-receipt tolerance as a fraction (0–1).
    # 0 → strict reject; 0.05 → 5% tolerance (ISO 9001 industry default).
    GR_OVER_RECEIPT_TOLERANCE: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)

    # ── e-Invoice / MyInvois ─────────────────────────────────────────────────
    # Adapter selection. "mock" is offline and deterministic — the demo default.
    # "sandbox" / "production" hit LHDN and require credentials below.
    # API/portal base URLs are derived from this value, never configured
    # separately, so a preprod credential cannot be aimed at production.
    MYINVOIS_MODE: Literal["mock", "sandbox", "production"] = "mock"
    MYINVOIS_CLIENT_ID: str = ""
    MYINVOIS_CLIENT_SECRET: str = ""
    # Intermediary TIN — only set when submitting on behalf of another taxpayer.
    MYINVOIS_ON_BEHALF_OF: str = ""
    MYINVOIS_TIMEOUT_SECONDS: float = 30.0
    # LHDN validates asynchronously. We poll this many times before parking the
    # invoice in SUBMITTED and letting the Celery reconciler finish the job.
    MYINVOIS_POLL_ATTEMPTS: int = 3
    MYINVOIS_POLL_INTERVAL_SECONDS: float = 2.0
    # XAdES signing (document v1.1) is not implemented — it needs an X.509
    # certificate from a Malaysian licensed CA. Enabling this fails loudly at
    # adapter construction rather than silently submitting unsigned documents.
    MYINVOIS_SIGN_ENABLED: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def redis_url(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}"

    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or f"{self.redis_url}/{self.REDIS_DB_DEFAULT}"

    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or f"{self.redis_url}/{self.REDIS_DB_DEFAULT}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
