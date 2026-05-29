from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "cipher"
    database_url: str = "sqlite:///./adpt.db"
    redis_url: str = "redis://localhost:6379/0"
    backend_session_secret: str = "dev-secret"
    init_db_on_startup: bool = True
    auth_trust_dev_headers: bool = True
    analysis_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.2"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    voyage_api_key: str | None = None
    voyage_embedding_model: str = "voyage-2"
    frontend_origin: str = "http://localhost:3000"
    free_tier_refresh_days: int = 14

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
