"""
app/core/config.py

WHY: Type-safe, validated, IDE-friendly config.
     Fails loudly at startup if anything is missing or wrong.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Security
    secret_key: str = Field(..., min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Database
    postgres_user: str = "stt_user"
    postgres_password: str = "stt_password"
    postgres_db: str = "stt_platform"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Storage
    storage_backend: Literal["local", "s3"] = "local"
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 500

    # Whisper
    whisper_model_size: Literal["tiny", "base", "small", "medium", "large-v3"] = "base"
    whisper_device: Literal["cpu", "cuda"] = "cpu"
    whisper_compute_type: Literal["int8", "float16", "float32"] = "int8"

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()