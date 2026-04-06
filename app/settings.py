from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "Autonomous Research Agent"
    log_level: str = "INFO"

    max_sources_default: int = Field(default=20, ge=1, le=50)
    max_queries_per_plan: int = Field(default=6, ge=1, le=12)
    global_run_timeout_minutes: int = Field(default=20, ge=1, le=120)
    per_url_timeout_seconds: int = Field(default=20, ge=5, le=120)
    llm_token_budget_per_run: int = Field(default=25_000, ge=1_000)
    fetch_max_concurrency: int = Field(default=8, ge=1, le=25)
    extraction_min_chars: int = Field(default=700, ge=200, le=10000)
    summary_chunk_chars: int = Field(default=3000, ge=500, le=10000)
    summary_chunk_overlap: int = Field(default=300, ge=0, le=2000)
    max_summary_chunks_per_source: int = Field(default=4, ge=1, le=12)
    min_relevance_score: float = Field(default=0.45, ge=0.0, le=1.0)
    notion_version: str = "2022-06-28"
    notion_request_timeout_seconds: int = Field(default=20, ge=5, le=120)
    gmail_request_timeout_seconds: int = Field(default=20, ge=5, le=120)
    slack_request_timeout_seconds: int = Field(default=10, ge=3, le=60)
    hard_max_sources: int = Field(default=50, ge=1, le=100)
    hard_max_queries_per_plan: int = Field(default=12, ge=1, le=30)
    hard_llm_token_budget_per_run: int = Field(default=120_000, ge=1_000)
    request_max_chars: int = Field(default=1000, ge=100, le=10000)
    alert_failure_threshold: int = Field(default=3, ge=1, le=100)
    alert_window_minutes: int = Field(default=60, ge=1, le=1440)

    llm_provider: Literal["openai", "anthropic"] = "openai"
    openai_model_planner: str = "gpt-5-mini"
    openai_model_summarizer: str = "gpt-5-mini"
    openai_model_reporter: str = "gpt-5"
    anthropic_model_planner: str = "claude-3-7-sonnet-latest"
    anthropic_model_summarizer: str = "claude-3-7-sonnet-latest"
    anthropic_model_reporter: str = "claude-3-7-sonnet-latest"

    openai_api_key: str | None = None
    tavily_api_key: str | None = None
    notion_token: str | None = None
    notion_database_id: str | None = None
    gmail_client_id: str | None = None
    gmail_client_secret: str | None = None
    gmail_refresh_token: str | None = None
    gmail_sender_email: str | None = None

    slack_webhook_url: str | None = None
    sentry_dsn: str | None = None

    def assert_required_secrets(self) -> None:
        required = {
            "OPENAI_API_KEY": self.openai_api_key,
            "TAVILY_API_KEY": self.tavily_api_key,
            "NOTION_TOKEN": self.notion_token,
            "NOTION_DATABASE_ID": self.notion_database_id,
            "GMAIL_CLIENT_ID": self.gmail_client_id,
            "GMAIL_CLIENT_SECRET": self.gmail_client_secret,
            "GMAIL_REFRESH_TOKEN": self.gmail_refresh_token,
            "GMAIL_SENDER_EMAIL": self.gmail_sender_email,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            missing_csv = ", ".join(missing)
            raise RuntimeError(
                "Missing required environment variables: "
                f"{missing_csv}. Copy .env.example to .env and set these values."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
