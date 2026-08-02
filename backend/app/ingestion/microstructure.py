"""Market Microstructure data ingestion (options flow, short interest, dark pool)."""

import logging
from typing import Any

from app.ingestion.finnhub_rest import FinnhubRESTClient
from app.utils.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class MicrostructureClient:
    """Client for fetching market microstructure data (short interest, etc.).
    
    Currently uses Finnhub as the primary source for this data, 
    but abstracted to allow adding other providers later.
    """
    
    def __init__(self, api_key: str | None = None) -> None:
        """Initialize with an underlying Finnhub client."""
        self.client = FinnhubRESTClient(api_key=api_key)
        
    async def get_basic_financials(self, ticker: str) -> dict[str, Any]:
        """Fetch basic financials which includes short interest, beta, etc.
        
        Note: True options flow and dark pool data often requires premium APIs.
        This provides the available foundational microstructure data.
        """
        # The underlying client has rate limiting
        await rate_limiter.acquire("finnhub")
        try:
            response = await self.client.client.get(
                "/stock/metric",
                params={"symbol": ticker, "metric": "all"}
            )
            response.raise_for_status()
            
            data = response.json()
            metrics = data.get("metric", {})
            
            # Extract the microstructure-relevant fields
            return {
                "ticker": ticker,
                "beta": metrics.get("beta"),
                "short_interest": metrics.get("shortInterest"),
                "short_ratio": metrics.get("shortRatio"),
                "52_week_high": metrics.get("52WeekHigh"),
                "52_week_low": metrics.get("52WeekLow"),
                "volume_avg_10d": metrics.get("10DayAverageTradingVolume"),
            }
            
        except Exception as e:
            logger.error(f"Error fetching microstructure for {ticker}: {e}")
            raise
            
    async def close(self) -> None:
        """Close the underlying client."""
        await self.client.close()
