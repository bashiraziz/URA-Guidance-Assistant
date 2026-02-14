from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "URA Guidance API"
    app_env: str = "development"
    app_debug: bool = True

    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5432/ura_guidance")
    sql_echo: bool = False
    db_pool_size: int = 3
    db_max_overflow: int = 2
    db_pool_timeout_seconds: int = 30

    api_jwt_secret: str = Field(default="dev-change-me")
    api_jwt_algorithm: str = "HS256"
    api_jwt_issuer: str = "ura-guidance-web"
    api_jwt_audience: str = "ura-guidance-api"

    retriever_mode: Literal["fts", "pgvector", "qdrant"] = "fts"
    retriever_top_k: int = 6

    gemini_enabled: bool = False
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"

    quota_daily_requests: int = 25
    quota_daily_output_tokens: int = 2000
    quota_minute_requests: int = 10
    quota_inflight_requests: int = 1

    docs_root: str = str((Path(__file__).resolve().parents[3] / "docs").resolve())
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
