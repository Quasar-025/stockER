"""Finnhub REST API client for company news and basic financials."""

import logging
from typing import Any

import httpx

from app.config import settings
from app.utils.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class FinnhubRESTClient:
    """Client for Finnhub REST API."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize with API key from settings if not provided."""
        self.api_key = api_key or settings.FINNHUB_API_KEY
        if not self.api_key:
            raise ValueError("Finnhub API key is required")

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            params={"token": self.api_key},
            timeout=10.0,
        )

    async def get_company_news(
        self, ticker: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """Fetch company news for a specific ticker and date range.

        Dates must be in YYYY-MM-DD format.
        """
        await rate_limiter.acquire("finnhub")

        try:
            response = await self.client.get(
                "/company-news", params={"symbol": ticker, "from": start_date, "to": end_date}
            )
            response.raise_for_status()

            # Finnhub returns a list of news dicts
            data = response.json()
            if not isinstance(data, list):
                logger.error(f"Unexpected response format from Finnhub: {data}")
                return []

            return data

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching news for {ticker}: {e}")
            raise

    async def get_company_profile(self, ticker: str) -> dict[str, Any]:
        """Fetch basic company profile (sector, industry, country)."""
        await rate_limiter.acquire("finnhub")

        try:
            response = await self.client.get("/stock/profile2", params={"symbol": ticker})
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching profile for {ticker}: {e}")
            raise

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
