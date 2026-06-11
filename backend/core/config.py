"""
Centralised application settings, loaded from environment variables / .env file.

Usage anywhere in the backend:

    from backend.core.config import settings

    print(settings.ARANGO_URL)
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All fields map 1-to-1 to the variables documented in .env.example.
    pydantic-settings reads them from the process environment first,
    then falls back to the .env file at the repository root.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # -- Ollama --
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"

    # -- ArangoDB --
    ARANGO_URL: str = "http://localhost:8529"
    ARANGO_DB: str = "ticket_agent"
    ARANGO_USER: str = "root"
    ARANGO_PASSWORD: str = ""

    # -- Redis --
    REDIS_URL: str = "redis://localhost:6379"

    # -- Embeddings --
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # -- Routing --
    CONFIDENCE_THRESHOLD: float = Field(default=0.70, ge=0.0, le=1.0)

    # -- Auth / JWT --
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # -- Logging --
    LOG_LEVEL: str = "INFO"


settings = Settings()
