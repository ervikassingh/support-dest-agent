from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    port: int = 8000
    rag_url: str = "http://localhost:8001"
    mcp_url: str = "http://localhost:8002/mcp"
    database_url: str = "postgresql://support:support@localhost:5432/support_desk"


settings = Settings()
