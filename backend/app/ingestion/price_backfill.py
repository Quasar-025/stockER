"""Backfill OHLCV data into TimescaleDB for any set of tickers.

Handles upsert semantics (safe to re-run) and also downloads the market
benchmark (SPY) and sector ETFs so that factor decomposition in the
intelligence layer has the inputs it needs.
"""

import logging
from datetime import date, datetime, timezone
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.yahoo_finance import MARKET_BENCHMARK, YahooFinanceClient

logger = logging.getLogger(__name__)


class PriceBackfillService:
    """Download and persist OHLCV data for a set of tickers."""

    def __init__(self, session: AsyncSession, client: YahooFinanceClient | None = None) -> None:
        self.session = session
        self.client = client or YahooFinanceClient()

    async def backfill(
        self,
        tickers: Sequence[str],
        start: str | date = "2008-01-01",
        end: str | date | None = None,
        *,
        include_benchmark: bool = True,
    ) -> dict[str, int]:
        """Download and upsert OHLCV for *tickers*.

        Returns ``{ticker: rows_upserted}`` counts.
        """
        all_tickers = list(tickers)
        if include_benchmark and MARKET_BENCHMARK not in all_tickers:
            all_tickers.append(MARKET_BENCHMARK)

        results: dict[str, int] = {}

        for ticker in all_tickers:
            try:
                rows = self.client.download_ohlcv(ticker, start, end)
                if not rows:
                    results[ticker] = 0
                    continue

                count = await self._upsert_ohlcv(rows)
                results[ticker] = count
                logger.info(f"Upserted {count} OHLCV rows for {ticker}")

            except Exception as e:
                logger.error(f"Backfill failed for {ticker}: {e}")
                results[ticker] = 0

        return results

    async def backfill_sector_etfs(
        self,
        sectors: Sequence[str],
        start: str | date = "2008-01-01",
        end: str | date | None = None,
    ) -> dict[str, int]:
        """Download OHLCV for sector ETFs that correspond to *sectors*."""
        etf_tickers = set()
        for sector in sectors:
            etf = self.client.sector_etf_for(sector)
            if etf:
                etf_tickers.add(etf)

        if not etf_tickers:
            return {}

        return await self.backfill(list(etf_tickers), start, end, include_benchmark=False)

    async def _upsert_ohlcv(self, rows: list[dict]) -> int:
        """Upsert OHLCV rows using ON CONFLICT (safe to re-run)."""
        if not rows:
            return 0

        stmt = text("""
            INSERT INTO ohlcv (time, ticker, open, high, low, close, volume)
            VALUES (:time, :ticker, :open, :high, :low, :close, :volume)
            ON CONFLICT (ticker, time) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """)

        await self.session.execute(stmt, rows)
        await self.session.commit()
        return len(rows)
