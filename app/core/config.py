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
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    DOKU_CLIENT_ID: str = ""
    DOKU_SECRET_KEY: str = ""
    DOKU_BASE_URL: str = "https://api-sandbox.doku.com"
    DOKU_CHECKOUT_PATH: str = "/checkout/v1/payment"
    DOKU_PAYMENT_DUE_MINUTES: int = 60
    DOKU_NOTIFICATION_PATH: str = "/api/v1/webhooks/doku"
    DOKU_NOTIFICATION_BASE_URL: str = ""
    DOKU_CALLBACK_URL: str = "http://localhost:3000/payment/result"

    # DOKU Direct API (BI-SNAP). Keys are file paths; never commit private keys.
    DOKU_SNAP_PARTNER_ID: str = ""
    DOKU_SNAP_CLIENT_SECRET: str = ""
    DOKU_SNAP_PRIVATE_KEY_PATH: str = ""
    DOKU_SNAP_DOKU_PUBLIC_KEY_PATH: str = ""
    DOKU_SNAP_DOKU_CLIENT_ID: str = ""
    DOKU_SNAP_VA_CHANNELS_JSON: str = "{}"
    DOKU_SNAP_CHANNEL_ID: str = "H2H"
    DOKU_SNAP_TOKEN_PATH: str = "/authorization/v1/access-token/b2b"
    DOKU_SNAP_VA_CREATE_PATH: str = "/virtual-accounts/bi-snap-va/v1.1/transfer-va/create-va"
    DOKU_SNAP_MERCHANT_TOKEN_PATH: str = "/api/v1/doku/snap/authorization/v1/access-token/b2b"
    DOKU_SNAP_VA_NOTIFICATION_PATH: str = "/api/v1/webhooks/doku/snap/va/payment"
    DOKU_SNAP_TOKEN_TTL_SECONDS: int = 900
    DOKU_SNAP_TIMESTAMP_TOLERANCE_SECONDS: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
