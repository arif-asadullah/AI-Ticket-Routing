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

    # -- LLM performance (latency tuning for on-prem / laptop inference) --
    # Keep the model resident in Ollama so tickets don't pay a cold model reload.
    LLM_KEEP_ALIVE: str = "30m"
    # Cap generated tokens — generation time scales with output length. The
    # classifier only needs a short JSON; the resolution a few steps.
    LLM_CLASSIFY_MAX_TOKENS: int = 300
    LLM_RESOLUTION_MAX_TOKENS: int = 450
    # Warm the model on startup (non-blocking) so the first ticket is fast.
    LLM_WARMUP_ON_STARTUP: bool = True
    # Generate the AI resolution inline (blocks the response on a 2nd LLM call).
    # Off by default: classification returns fast, resolution is generated lazily.
    GENERATE_RESOLUTION_INLINE: bool = False

    # -- Self-learning: correction precedent --
    # When a new ticket is near-identical to a past human correction, adopt that
    # verified category (deterministic exact-cosine over the small corrections set,
    # so it never gets drowned out by the approximate nearest-neighbour index).
    CORRECTION_PRECEDENT_ENABLED: bool = True
    CORRECTION_PRECEDENT_MIN_SIMILARITY: float = Field(default=0.80, ge=0.0, le=1.0)
    # Auto-recompute category centroids after a trusted correction (background,
    # throttled) so the centroid classifier learns without a manual admin call.
    AUTO_RECOMPUTE_CENTROIDS: bool = True
    AUTO_RECOMPUTE_MIN_NEW_CORRECTIONS: int = Field(default=1, ge=1)

    # -- Auth / JWT --
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # -- Logging --
    LOG_LEVEL: str = "INFO"


settings = Settings()
