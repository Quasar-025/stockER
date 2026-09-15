"""Application configuration via environment variables.

All settings are loaded from a .env file. Required settings will cause
a startup error if not provided, ensuring no accidental runs with
missing credentials.
"""

import json
from pathlib import Path
from urllib.parse import quote
from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve configuration relative to this source file rather than the process
# working directory. Alembic runs from ``backend/`` while Docker Compose and
# the documented setup keep ``.env`` at the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """StockER application settings.

    Required fields have no default and MUST be set in .env.
    Optional fields default to None and are checked at runtime.
    """

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- App ---
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = '["http://localhost:3000", "http://localhost:3001"]'

    # --- Database (REQUIRED) ---
    DATABASE_URL: str  # No default → must be in .env
    DATABASE_SYNC_URL: str
    # Local Compose credentials.  Keep URLs as settings too for remote/custom
    # deployments, but derive localhost URLs from these values so dotenv
    # interpolation and reserved password characters cannot alter credentials.
    POSTGRES_DB: str = "stocker"
    POSTGRES_USER: str = "stocker"
    POSTGRES_PASSWORD: str | None = None
    # Explicit IPv4 avoids a Windows ``localhost`` lookup connecting to an
    # unrelated PostgreSQL service listening only on ``::1``.
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432

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

    def _local_database_url(self, dialect: str, fallback: str) -> str:
        """Return one unambiguous local URL when Compose credentials exist.

        ``DATABASE_URL`` remains available for a remote deployment. For the
        documented local Docker stack, the discrete ``POSTGRES_*`` settings
        are authoritative. This prevents a stale shell URL, dotenv
        interpolation, URL escaping, or an IPv6-only localhost service from
        changing the password or selecting another database instance.
        """
        if not self.POSTGRES_PASSWORD:
            return fallback

        user = quote(self.POSTGRES_USER, safe="")
        password = quote(self.POSTGRES_PASSWORD, safe="")
        database = quote(self.POSTGRES_DB, safe="")
        host = self.POSTGRES_HOST.strip() or "127.0.0.1"
        return f"{dialect}://{user}:{password}@{host}:{self.POSTGRES_PORT}/{database}"

    @property
    def database_url(self) -> str:
        """Effective async URL used by the application and Alembic."""
        return self._local_database_url("postgresql+asyncpg", self.DATABASE_URL)

    @property
    def database_sync_url(self) -> str:
        """Effective sync URL for scripts that require psycopg."""
        return self._local_database_url("postgresql+psycopg", self.DATABASE_SYNC_URL)

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS JSON string to list."""
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:3000", "http://localhost:3001"]

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
