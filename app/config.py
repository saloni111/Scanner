"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    # Database
    database_url: str = Field(
        default="postgresql+psycopg2://scanner:scanner@localhost:5432/scanner"
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        """Accept the postgres:// scheme some hosts hand out (Heroku, Render)
        and the bare postgresql:// scheme; both get the psycopg2 driver."""
        if v.startswith("postgres://"):
            return "postgresql+psycopg2://" + v[len("postgres://") :]
        if v.startswith("postgresql://") and "+psycopg2" not in v:
            return "postgresql+psycopg2://" + v[len("postgresql://") :]
        return v

    # LLM
    openai_api_key: str = Field(default="")
    llm_model: str = Field(default="gpt-4o-mini")
    embedding_model: str = Field(default="text-embedding-3-small")

    # GitHub
    github_token: str = Field(default="")
    github_webhook_secret: str = Field(default="")

    # Scanner limits
    max_files_per_scan: int = Field(default=200)
    max_file_size_kb: int = Field(default=500)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
