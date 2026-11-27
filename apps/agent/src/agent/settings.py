from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    port: int = 8000
    rag_url: str = "http://localhost:8001"
    mcp_url: str = "http://localhost:8002/mcp"
    database_url: str = "postgresql://support:support@localhost:5432/support_desk"

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # OpenRouter model ids. Swap either slug without changing code.
    cheap_model: str = "openai/gpt-4o-mini"
    main_model: str = "anthropic/claude-haiku-4.5"
    context_token_budget: int = 128_000
    summarize_threshold_ratio: float = 0.7
    keep_recent_messages: int = 8

    email_provider: str = "stub"  # stub | resend (resend not wired yet)
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "support-desk-agent"


settings = Settings()
