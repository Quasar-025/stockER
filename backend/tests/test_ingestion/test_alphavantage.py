"""Tests for the Alpha Vantage REST client."""

import pytest
import httpx
from unittest.mock import patch, AsyncMock

from app.ingestion.alphavantage import AlphaVantageClient


@pytest.fixture
def mock_alphavantage_api_key(monkeypatch):
    """Mock the API key setting."""
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test_api_key")


@pytest.mark.asyncio
async def test_alphavantage_client_requires_api_key(monkeypatch):
    """Test that missing API key raises ValueError."""
    monkeypatch.setattr("app.config.settings.ALPHAVANTAGE_API_KEY", "")
    
    with pytest.raises(ValueError, match="Alpha Vantage API key is required"):
        AlphaVantageClient()


@pytest.mark.asyncio
async def test_get_news_sentiment():
    """Test fetching news sentiment."""
    client = AlphaVantageClient(api_key="test_api_key")
    
    mock_response = httpx.Response(200, json={
        "items": 50,
        "sentiment_score_definition": "x",
        "relevance_score_definition": "y",
        "feed": [
            {
                "title": "Stock market rally continues",
                "url": "https://example.com",
                "time_published": "20240101T000000",
                "authors": ["John Doe"],
                "summary": "Market up",
                "overall_sentiment_score": 0.35,
                "overall_sentiment_label": "Somewhat-Bullish",
                "ticker_sentiment": [
                    {
                        "ticker": "AAPL",
                        "relevance_score": "0.9",
                        "ticker_sentiment_score": "0.45",
                        "ticker_sentiment_label": "Bullish"
                    }
                ]
            }
        ]
    })
    
    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        with patch("app.ingestion.alphavantage.rate_limiter.acquire", new_callable=AsyncMock) as mock_acquire:
            data = await client.get_news_sentiment("AAPL")
            
            mock_acquire.assert_called_once_with("alphavantage")
            mock_get.assert_called_once()
            
            assert len(data["feed"]) == 1
            assert data["feed"][0]["title"] == "Stock market rally continues"
            assert data["feed"][0]["ticker_sentiment"][0]["ticker"] == "AAPL"

    await client.close()


@pytest.mark.asyncio
async def test_get_news_sentiment_rate_limit_graceful():
    """Test handling of the rate limit error response from Alpha Vantage."""
    client = AlphaVantageClient(api_key="test_api_key")
    
    # Alpha Vantage returns 200 OK even when rate limit is hit, just with an Information key
    mock_response = httpx.Response(200, json={
        "Information": "Thank you for using Alpha Vantage! Our standard API rate limit is 25 requests per day."
    })
    
    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        with patch("app.ingestion.alphavantage.rate_limiter.acquire", new_callable=AsyncMock):
            data = await client.get_news_sentiment("AAPL")
            
            # The client should catch the rate limit message and return an empty feed
            # instead of raising a KeyError later in the pipeline
            assert data == {"feed": []}

    await client.close()
