"""SEC EDGAR RSS Feed Monitor for recent company filings (8-K, 10-K, 10-Q)."""

import logging
from typing import Any

import feedparser
import httpx

from app.utils.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class SecEdgarClient:
    """Client for SEC EDGAR RSS feeds and filing endpoints.
    
    The SEC requires a User-Agent header with a valid email address.
    """
    
    BASE_RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
    
    def __init__(self, user_agent: str = "StockER/0.1.0 (info@stocker.dev)") -> None:
        """Initialize the client."""
        self.user_agent = user_agent
        self.client = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=15.0,
        )
        
    async def get_latest_filings(self, ticker: str, filing_type: str = "") -> list[dict[str, Any]]:
        """Fetch the latest filings for a given ticker via RSS."""
        await rate_limiter.acquire("sec_edgar")
        
        try:
            # Construct the query params for the RSS feed
            # action=getcompany&CIK={ticker}&type={filing_type}&output=atom
            params = {
                "action": "getcompany",
                "CIK": ticker,
                "type": filing_type,
                "output": "atom",
                "count": 10
            }
            
            response = await self.client.get(self.BASE_RSS_URL, params=params)
            response.raise_for_status()
            
            # Parse the ATOM/RSS feed
            feed = feedparser.parse(response.text)
            
            filings = []
            for entry in feed.entries:
                # The SEC feed puts the filing type in the summary or category
                filings.append({
                    "title": entry.title,
                    "link": entry.link,
                    "updated": entry.updated,
                    "summary": entry.summary if hasattr(entry, "summary") else "",
                })
                
            return filings
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching SEC filings for {ticker}: {e}")
            raise
            
    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
