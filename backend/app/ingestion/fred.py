"""Federal Reserve Economic Data (FRED) REST API client."""

import logging
from typing import Any

import httpx

from app.config import settings
from app.utils.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class FREDClient:
    """Client for FRED API to fetch macroeconomic indicators."""

    BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize with API key from settings if not provided."""
        self.api_key = api_key or settings.FRED_API_KEY
        if not self.api_key:
            raise ValueError("FRED API key is required")

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=15.0,
        )

    async def get_series_observations(self, series_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch observations (data points) for an economic series.

        Common Series IDs:
        - CPIAUCSL: Consumer Price Index (Inflation)
        - FEDFUNDS: Federal Funds Effective Rate (Interest Rates)
        - UNRATE: Unemployment Rate
        """
        await rate_limiter.acquire("fred")

        try:
            response = await self.client.get(
                "/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "limit": limit,
                    "sort_order": "desc",
                }
            )
            response.raise_for_status()

            data = response.json()
            return data.get("observations", [])

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching FRED series {series_id}: {e}")
            raise

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
