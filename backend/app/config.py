"""Application configuration via environment variables.

All settings are loaded from a .env file. Required settings will cause
a startup error if not provided, ensuring no accidental runs with
missing credentials.
"""

import json
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """StockER application settings.

    Required fields have no default and MUST be set in .env.
    Optional fields default to None and are checked at runtime.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- App ---
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = '["http://localhost:3000"]'

    # --- Database (REQUIRED) ---
    DATABASE_URL: str  # No default → must be in .env
    DATABASE_SYNC_URL: str

    # --- Redis (REQUIRED) ---
    REDIS_URL: str

    # --- Qdrant (REQUIRED) ---
    QDRANT_HOST: str
    QDRANT_PORT: int = 6333

    # --- Neo4j (REQUIRED) ---
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str

    # --- Redpanda / Kafka (REQUIRED) ---
    KAFKA_BOOTSTRAP_SERVERS: str

    # --- API Keys (REQUIRED for data ingestion) ---
    FINNHUB_API_KEY: str
    ALPHAVANTAGE_API_KEY: str
    FRED_API_KEY: str

    # --- LLM (REQUIRED — at least Ollama) ---
    OLLAMA_HOST: str
    OLLAMA_MODEL: str

    # --- Optional cloud LLM providers ---
    OPENAI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None

    # --- Embeddings (REQUIRED) ---
    EMBEDDING_PROVIDER: str  # "ollama" or "openai"
    EMBEDDING_MODEL: str

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS JSON string to list."""
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:3000"]

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.APP_ENV == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in test mode."""
        return self.APP_ENV == "testing"

    @property
    def has_openai(self) -> bool:
        """Check if OpenAI API key is configured."""
        return self.OPENAI_API_KEY is not None and len(self.OPENAI_API_KEY) > 0

    @property
    def has_google(self) -> bool:
        """Check if Google API key is configured."""
        return self.GOOGLE_API_KEY is not None and len(self.GOOGLE_API_KEY) > 0


# Loaded at import time — will raise ValidationError if .env is missing required fields
settings = Settings()
