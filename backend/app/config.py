from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "高校学术活动智能推荐与问答平台"
    database_url: str = "sqlite:///./data/campus_seminar.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    admin_token: str = ""
    max_upload_mb: int = 10
    retrieval_provider: str = "sqlite"
    milvus_uri: str = ""
    milvus_collection: str = "campus_events"
    embedding_provider: str = "deterministic"
    llm_provider: str = "template"
    openai_api_key: str = ""
    crawl_timeout_seconds: float = 10.0
    crawl_retries: int = 2
    crawl_delay_seconds: float = 0.5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]

    @property
    def data_dir(self) -> Path:
        return Path(__file__).resolve().parents[1] / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()

