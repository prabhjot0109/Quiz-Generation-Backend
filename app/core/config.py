from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Peblo Quiz Backend"
    environment: Literal["local", "test", "staging", "production"] = "local"
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/peblo_db",
        alias="DATABASE_URL",
    )
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3-flash-preview", alias="GEMINI_MODEL")
    ai_request_timeout_seconds: float = Field(default=20.0, alias="AI_REQUEST_TIMEOUT_SECONDS")
    default_question_count: int = Field(default=5, alias="DEFAULT_QUESTION_COUNT")
    chunk_size: int = Field(default=900, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=120, alias="CHUNK_OVERLAP")
    ai_max_retries: int = Field(default=2, alias="AI_MAX_RETRIES")


@lru_cache
def get_settings() -> Settings:
    return Settings()
