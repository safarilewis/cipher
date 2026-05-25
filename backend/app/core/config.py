from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "cipher"
    database_url: str = "sqlite:///./adpt.db"
    redis_url: str = "redis://localhost:6379/0"
    backend_session_secret: str = "dev-secret"
    auth_trust_dev_headers: bool = True
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.2"
    frontend_origin: str = "http://localhost:3000"
    free_tier_refresh_days: int = 14

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
