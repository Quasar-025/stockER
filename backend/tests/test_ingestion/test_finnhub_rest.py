"""Tests for the Finnhub REST client."""

import pytest
import httpx
from unittest.mock import patch, AsyncMock

from app.ingestion.finnhub_rest import FinnhubRESTClient


@pytest.fixture
def mock_finnhub_api_key(monkeypatch):
    """Mock the API key setting."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test_api_key")
    # Need to reload settings or just pass directly to constructor in test


@pytest.mark.asyncio
async def test_finnhub_client_requires_api_key(monkeypatch):
    """Test that missing API key raises ValueError."""
    # Ensure settings.FINNHUB_API_KEY is empty for this test
    monkeypatch.setattr("app.config.settings.FINNHUB_API_KEY", "")
    
    with pytest.raises(ValueError, match="Finnhub API key is required"):
        FinnhubRESTClient()


@pytest.mark.asyncio
async def test_get_company_news():
    """Test fetching company news."""
    client = FinnhubRESTClient(api_key="test_api_key")
    
    # Mock the underlying httpx client
    mock_response = httpx.Response(200, json=[
        {
            "category": "company",
            "datetime": 1596589501,
            "headline": "Apple is doing great",
            "id": 12345,
            "image": "https://example.com/image.jpg",
            "related": "AAPL",
            "source": "Yahoo",
            "summary": "Apple summary...",
            "url": "https://example.com/news"
        }
    ])
    
    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        # We need to mock the rate limiter so we don't actually sleep in tests
        with patch("app.ingestion.finnhub_rest.rate_limiter.acquire", new_callable=AsyncMock) as mock_acquire:
            news = await client.get_company_news("AAPL", "2024-01-01", "2024-01-31")
            
            mock_acquire.assert_called_once_with("finnhub")
            mock_get.assert_called_once()
            
            assert len(news) == 1
            assert news[0]["headline"] == "Apple is doing great"
            assert news[0]["related"] == "AAPL"

    await client.close()
