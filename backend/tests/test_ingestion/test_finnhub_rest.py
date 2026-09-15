"""Tests for the Finnhub REST client."""

import pytest
import httpx
from unittest.mock import patch, AsyncMock

from app.ingestion.finnhub_rest import FinnhubRESTClient


def _mock_response(status_code: int = 200, json_data=None, text_data: str = "") -> httpx.Response:
    """Create a properly constructed mock httpx Response."""
    request = httpx.Request("GET", "https://test.example.com")
    if json_data is not None:
        return httpx.Response(status_code, json=json_data, request=request)
    return httpx.Response(status_code, text=text_data, request=request)


@pytest.mark.asyncio
async def test_finnhub_client_requires_api_key(monkeypatch):
    """Test that missing API key raises ValueError."""
    monkeypatch.setattr("app.config.settings.FINNHUB_API_KEY", "")
    with pytest.raises(ValueError, match="Finnhub API key is required"):
        FinnhubRESTClient()


@pytest.mark.asyncio
async def test_get_company_news():
    """Test fetching company news."""
    client = FinnhubRESTClient(api_key="test_api_key")

    mock_resp = _mock_response(json_data=[
        {
            "category": "company",
            "datetime": 1596589501,
            "headline": "Apple is doing great",
            "id": 12345,
            "image": "https://example.com/image.jpg",
            "related": "AAPL",
            "source": "Yahoo",
            "summary": "Apple summary...",
            "url": "https://example.com/news",
        }
    ])

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        with patch("app.ingestion.finnhub_rest.rate_limiter.acquire", new_callable=AsyncMock) as mock_acq:
            news = await client.get_company_news("AAPL", "2024-01-01", "2024-01-31")
            mock_acq.assert_called_once_with("finnhub")
            assert len(news) == 1
            assert news[0]["headline"] == "Apple is doing great"

    await client.close()
