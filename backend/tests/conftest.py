"""StockER test configuration.

This conftest sets up all required environment variables BEFORE any app
modules are imported, so that `app.config.settings` can initialize
without a real .env file.
"""

import os
import pytest

# ================================================================
# Set test environment variables BEFORE importing app modules.
# This must happen at conftest load time, before any test collects.
# ================================================================
_TEST_ENV = {
    "APP_ENV": "testing",
    "LOG_LEVEL": "WARNING",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/stocker_test",
    "DATABASE_SYNC_URL": "postgresql+psycopg://test:test@localhost:5432/stocker_test",
    "REDIS_URL": "redis://localhost:6379/1",
    "QDRANT_HOST": "localhost",
    "QDRANT_PORT": "6333",
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": "test_password",
    "KAFKA_BOOTSTRAP_SERVERS": "localhost:19092",
    "FINNHUB_API_KEY": "test_finnhub_key",
    "ALPHAVANTAGE_API_KEY": "test_alphavantage_key",
    "FRED_API_KEY": "test_fred_key",
    "OLLAMA_HOST": "http://localhost:11434",
    "OLLAMA_MODEL": "test-model",
    "EMBEDDING_PROVIDER": "ollama",
    "EMBEDDING_MODEL": "nomic-embed-text",
    "CORS_ORIGINS": '["http://localhost:3000"]',
}

for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)


@pytest.fixture
def anyio_backend():
    """Use asyncio as the async backend for tests."""
    return "asyncio"
