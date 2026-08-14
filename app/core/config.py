from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "IWBIF 2026 Event Portal"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/event_portal"
    APP_SECRET_KEY: str = "change_me"
    JWT_SECRET_KEY: str = "change_me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    FRONTEND_URL: str = "http://localhost:3000"
    UPLOAD_DIR: str = "uploads"
    UPLOAD_URL_PREFIX: str = "/uploads"
    PROFILE_PHOTO_MAX_SIZE_BYTES: int = 5 * 1024 * 1024

    PROJECT_TIMEZONE: str = "Asia/Jakarta"

    DOKU_CLIENT_ID: str = ""
    DOKU_SECRET_KEY: str = ""
    DOKU_BASE_URL: str = "https://api-sandbox.doku.com"
    DOKU_CHECKOUT_PATH: str = "/checkout/v1/payment"
    DOKU_PAYMENT_DUE_MINUTES: int = 60
    DOKU_NOTIFICATION_PATH: str = "/api/v1/webhooks/doku"
    DOKU_CALLBACK_URL: str = "http://localhost:3000/payment/result"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
