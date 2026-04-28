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
