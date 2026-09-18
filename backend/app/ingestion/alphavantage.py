"""Alpha Vantage REST API client for news sentiment and fundamental data."""

import logging
from typing import Any

import httpx

from app.config import settings
from app.utils.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class AlphaVantageClient:
    """Client for Alpha Vantage REST API."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize with API key from settings if not provided."""
        self.api_key = api_key or settings.ALPHAVANTAGE_API_KEY
        if not self.api_key:
            raise ValueError("Alpha Vantage API key is required")

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=15.0,
        )

    async def get_news_sentiment(self, ticker: str) -> dict[str, Any]:
        """Fetch news and sentiment for a specific ticker.

        Note: The free tier allows 25 calls per day.
        """
        await rate_limiter.acquire("alphavantage")

        try:
            response = await self.client.get(
                "",
                params={
                    "function": "NEWS_SENTIMENT",
                    "tickers": ticker,
                    "apikey": self.api_key,
                }
            )
            response.raise_for_status()

            data = response.json()

            # Handle rate limit exceeded response gracefully
            if "Information" in data and "rate limit" in data["Information"].lower():
                logger.warning(f"Alpha Vantage rate limit exceeded: {data['Information']}")
                return {"feed": []}

            return data

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching news sentiment for {ticker}: {e}")
            raise

    async def get_company_overview(self, ticker: str) -> dict[str, Any]:
        """Fetch fundamental company overview data."""
        await rate_limiter.acquire("alphavantage")

        try:
            response = await self.client.get(
                "",
                params={
                    "function": "OVERVIEW",
                    "symbol": ticker,
                    "apikey": self.api_key,
                }
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching overview for {ticker}: {e}")
            raise

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
