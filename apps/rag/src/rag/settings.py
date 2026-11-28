"""Runtime configuration. Relative env files resolve from the process cwd."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    port: int = 8001
    database_url: str = "postgresql://support:support@localhost:5432/support_desk"
    redis_url: str = "redis://localhost:6379"
    uploads_dir: Path = _REPO / "data" / "uploads"

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    main_model: str = "anthropic/claude-haiku-4.5"
    judge_model: str = "openai/gpt-4.1"
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dim: int = 1536

    chunk_tokens: int = 800
    chunk_overlap: int = 100
    candidate_k: int = 50
    rrf_k: int = 60

    chat_input_usd_per_million: float | None = None
    chat_output_usd_per_million: float | None = None
    embedding_usd_per_million: float | None = None

    langsmith_api_key: str | None = None
    langsmith_project: str = "support-rag"
    worker_enabled: bool = True

    @property
    def uploads_path(self) -> Path:
        path = self.uploads_dir
        if not path.is_absolute():
            path = Path.cwd() / path
        return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
