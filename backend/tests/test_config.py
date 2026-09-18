"""Tests for application configuration."""


from app.config import Settings


def test_settings_loads_from_env():
    """Test that Settings loads values from environment variables."""
    settings = Settings()

    assert settings.APP_ENV == "testing"
    assert settings.FINNHUB_API_KEY == "test_finnhub_key"
    assert settings.QDRANT_PORT == 6333


def test_settings_cors_origins_list():
    """Test CORS origins parsing."""
    settings = Settings()

    origins = settings.cors_origins_list
    assert isinstance(origins, list)
    assert "http://localhost:3000" in origins


def test_settings_cors_origins_invalid_json(monkeypatch):
    """Test graceful fallback when CORS_ORIGINS is invalid JSON."""
    monkeypatch.setenv("CORS_ORIGINS", "not-valid-json")
    settings = Settings()
    assert settings.cors_origins_list == ["http://localhost:3000", "http://localhost:3001"]


def test_settings_is_testing():
    """Test the is_testing property."""
    settings = Settings()
    assert settings.is_testing is True
    assert settings.is_development is False


def test_settings_has_openai_false():
    """Test has_openai when no key is set."""
    settings = Settings()
    assert settings.has_openai is False


def test_settings_has_google_false():
    """Test has_google when no key is set."""
    settings = Settings()
    assert settings.has_google is False
