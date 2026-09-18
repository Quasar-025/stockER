"""Tests for the Alpha Vantage REST client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.ingestion.alphavantage import AlphaVantageClient


def _mock_response(status_code: int = 200, json_data=None) -> httpx.Response:
    """Create a properly constructed mock httpx Response."""
    request = httpx.Request("GET", "https://test.example.com")
    return httpx.Response(status_code, json=json_data, request=request)


@pytest.mark.asyncio
async def test_alphavantage_client_requires_api_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.ALPHAVANTAGE_API_KEY", "")
    with pytest.raises(ValueError, match="Alpha Vantage API key is required"):
        AlphaVantageClient()


@pytest.mark.asyncio
async def test_get_news_sentiment():
    client = AlphaVantageClient(api_key="test_api_key")

    mock_resp = _mock_response(json_data={
        "items": 50,
        "feed": [
            {
                "title": "Stock market rally continues",
                "url": "https://example.com",
                "time_published": "20240101T000000",
                "overall_sentiment_score": 0.35,
                "ticker_sentiment": [
                    {"ticker": "AAPL", "ticker_sentiment_score": "0.45"}
                ],
            }
        ],
    })

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        with patch("app.ingestion.alphavantage.rate_limiter.acquire", new_callable=AsyncMock):
            data = await client.get_news_sentiment("AAPL")
            assert len(data["feed"]) == 1
            assert data["feed"][0]["title"] == "Stock market rally continues"

    await client.close()


@pytest.mark.asyncio
async def test_get_news_sentiment_rate_limit_graceful():
    client = AlphaVantageClient(api_key="test_api_key")

    mock_resp = _mock_response(json_data={
        "Information": "Thank you for using Alpha Vantage! Our standard API rate limit is 25 requests per day."
    })

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        with patch("app.ingestion.alphavantage.rate_limiter.acquire", new_callable=AsyncMock):
            data = await client.get_news_sentiment("AAPL")
            assert data == {"feed": []}

    await client.close()
