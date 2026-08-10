from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-5"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    tavily_api_key: str | None = None

    database_url: str = "sqlite:///./research_crew.sqlite3"
    workspaces_dir: Path = Path("./workspaces")

    api_dev_key: str = "dev-local-key"
    cors_origins: str = "http://localhost:5173"

    max_revisions: int = 3
    code_exec_timeout_seconds: int = 10
    code_exec_memory_limit_mb: int = 256

    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "langgraph-research-crew"
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def uses_postgres(self) -> bool:
        return self.database_url.startswith("postgres")


@lru_cache
def get_settings() -> Settings:
    return Settings()
