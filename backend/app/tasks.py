"""Celery background tasks for data ingestion."""

import asyncio
import logging
from typing import Any

from app.worker import celery_app
from app.ingestion.sec_edgar import SecEdgarClient
from app.ingestion.fred import FREDClient
from app.streaming.events import EventProducer

logger = logging.getLogger(__name__)


def run_async(coro: Any) -> Any:
    """Helper to run async functions synchronously in Celery tasks."""
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(bind=True, name="app.tasks.fetch_latest_sec_filings")
def fetch_latest_sec_filings(self: Any, ticker: str = "AAPL") -> dict[str, Any]:
    """Fetch recent SEC filings and push to Redpanda stream."""
    logger.info(f"Starting SEC filings fetch for {ticker}")
    
    async def _fetch() -> dict[str, Any]:
        client = SecEdgarClient()
        producer = EventProducer()
        
        try:
            filings = await client.get_latest_filings(ticker)
            
            # Produce each filing to the raw news topic
            for filing in filings:
                producer.produce(
                    topic="raw_events",
                    key=f"sec_{ticker}_{filing['updated']}",
                    value={
                        "source": "sec_edgar",
                        "ticker": ticker,
                        "data": filing
                    }
                )
            
            producer.flush()
            return {"status": "success", "count": len(filings)}
        finally:
            await client.close()
            
    return run_async(_fetch())


@celery_app.task(bind=True, name="app.tasks.fetch_macro_indicators")
def fetch_macro_indicators(self: Any) -> dict[str, Any]:
    """Fetch macroeconomic data (FRED) and push to stream."""
    logger.info("Starting macro indicators fetch")
    
    async def _fetch() -> dict[str, Any]:
        client = FREDClient()
        producer = EventProducer()
        
        indicators = ["CPIAUCSL", "FEDFUNDS", "UNRATE"]
        results = {}
        
        try:
            for ind in indicators:
                observations = await client.get_series_observations(ind, limit=5)
                results[ind] = len(observations)
                
                producer.produce(
                    topic="raw_events",
                    key=f"fred_{ind}",
                    value={
                        "source": "fred",
                        "indicator": ind,
                        "data": observations
                    }
                )
                
            producer.flush()
            return {"status": "success", "counts": results}
        finally:
            await client.close()
            
    return run_async(_fetch())
