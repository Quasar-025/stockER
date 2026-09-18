"""Celery background tasks for data ingestion."""

import asyncio
import logging
from typing import Any

from app.ingestion.fred import FREDClient
from app.ingestion.sec_edgar import SecEdgarClient
from app.streaming.events import EventProducer
from app.worker import celery_app

logger = logging.getLogger(__name__)


def run_async(coro: Any) -> Any:
    """Helper to run async functions synchronously in Celery tasks."""
    return asyncio.run(coro)


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


@celery_app.task(bind=True, name="app.tasks.daily_price_update")
def daily_price_update(self: Any) -> dict[str, Any]:
    """Fetch daily OHLCV updates for all registered stocks."""
    logger.info("Starting daily price update via yfinance")

    async def _fetch() -> dict[str, Any]:
        from sqlalchemy import text

        from app.ingestion.price_backfill import PriceBackfillService
        from app.utils.database import async_session_factory

        async with async_session_factory() as db:
            # Get all active tickers
            result = await db.execute(text("SELECT ticker FROM stocks"))
            tickers = [row[0] for row in result.all()]

            if not tickers:
                return {"status": "skipped", "reason": "No stocks registered"}

            backfill = PriceBackfillService(session=db)

            # Fetch last 3 days to ensure no gaps
            from datetime import date, timedelta
            start_date = date.today() - timedelta(days=3)

            results = await backfill.backfill(tickers, start=start_date)
            total = sum(results.values())

            return {"status": "success", "tickers_processed": len(tickers), "rows_upserted": total}

    return run_async(_fetch())


@celery_app.task(bind=True, name="app.tasks.scheduled_news_ingestion")
def scheduled_news_ingestion(self: Any) -> dict[str, Any]:
    """Fetch daily Finnhub news for tracked companies and process events."""
    logger.info("Starting scheduled news ingestion")

    async def _fetch() -> dict[str, Any]:
        from sqlalchemy import text

        from app.services.ingestion_pipeline import IngestionPipeline
        from app.utils.database import async_session_factory

        async with async_session_factory() as db:
            result = await db.execute(text("SELECT ticker FROM stocks"))
            tickers = [row[0] for row in result.all()]

            pipeline = IngestionPipeline(session=db)

            # Try to set up Qdrant
            try:
                from app.vectors.store import QdrantEventStore
                pipeline.qdrant_store = QdrantEventStore()
            except Exception:
                pass

            total_processed = 0
            for ticker in tickers:
                events = await pipeline.ingest_ticker(ticker)
                total_processed += len(events)
                # Sleep briefly to respect Finnhub free tier rate limits (60/min)
                await asyncio.sleep(1.5)

            return {"status": "success", "events_processed": total_processed}

    return run_async(_fetch())
