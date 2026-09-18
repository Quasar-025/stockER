"""One-time bootstrap service: populate the database from scratch.

Orchestrates the full initial data load:
  1. Register stocks in the DB (via Finnhub profiles)
  2. Backfill OHLCV from 2008 to present (via yfinance)
  3. Compute historical outcomes for the 60 landmark events
  4. Embed landmark events in Qdrant for semantic search
"""

import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.outcome_collector import HistoricalOutcomeCollector
from app.ingestion.price_backfill import PriceBackfillService
from app.ingestion.yahoo_finance import YahooFinanceClient

logger = logging.getLogger(__name__)

LANDMARK_EVENTS_PATH = Path(__file__).resolve().parents[2] / "data" / "landmark_events.json"

# Initial set of tickers to track — the 8 seeded graph companies + major ETFs
INITIAL_TICKERS = [
    # Seeded graph companies
    "TSM",
    "NVDA",
    "AAPL",
    "AMD",
    "MSFT",
    "ORCL",
    # Major market ETFs
    "SPY",
    "QQQ",
    "DIA",
    "IWM",
    # Sector ETFs
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLC",
    "XLY",
    "XLP",
    "XLI",
    "XLB",
    "XLRE",
    "XLU",
    # Other commonly affected tickers from landmark events
    "TLT",
    "GLD",
    "USO",
    "EEM",
    "FXI",
    "META",
    "GOOGL",
    "AMZN",
]

# Stock info for the seeded tickers (avoids Finnhub API call at bootstrap)
SEED_STOCK_INFO: list[dict] = [
    {
        "ticker": "TSM",
        "name": "Taiwan Semiconductor Manufacturing",
        "sector": "Technology",
        "industry": "Semiconductors",
        "country": "TW",
        "exchange": "NYSE",
    },
    {
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors",
        "country": "US",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "country": "US",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "AMD",
        "name": "Advanced Micro Devices",
        "sector": "Technology",
        "industry": "Semiconductors",
        "country": "US",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "MSFT",
        "name": "Microsoft Corporation",
        "sector": "Technology",
        "industry": "Software",
        "country": "US",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "ORCL",
        "name": "Oracle Corporation",
        "sector": "Technology",
        "industry": "Software",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "SPY",
        "name": "SPDR S&P 500 ETF Trust",
        "sector": "N/A",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "QQQ",
        "name": "Invesco QQQ Trust",
        "sector": "N/A",
        "industry": "ETF",
        "country": "US",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "DIA",
        "name": "SPDR Dow Jones Industrial Average ETF",
        "sector": "N/A",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "IWM",
        "name": "iShares Russell 2000 ETF",
        "sector": "N/A",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "XLK",
        "name": "Technology Select Sector SPDR Fund",
        "sector": "Technology",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "XLF",
        "name": "Financial Select Sector SPDR Fund",
        "sector": "Financials",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "XLE",
        "name": "Energy Select Sector SPDR Fund",
        "sector": "Energy",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "XLV",
        "name": "Health Care Select Sector SPDR Fund",
        "sector": "Healthcare",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "XLC",
        "name": "Communication Services Select Sector SPDR Fund",
        "sector": "Communication Services",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "XLY",
        "name": "Consumer Discretionary Select Sector SPDR Fund",
        "sector": "Consumer Discretionary",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "XLP",
        "name": "Consumer Staples Select Sector SPDR Fund",
        "sector": "Consumer Staples",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "XLI",
        "name": "Industrial Select Sector SPDR Fund",
        "sector": "Industrials",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "XLB",
        "name": "Materials Select Sector SPDR Fund",
        "sector": "Materials",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "XLRE",
        "name": "Real Estate Select Sector SPDR Fund",
        "sector": "Real Estate",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "XLU",
        "name": "Utilities Select Sector SPDR Fund",
        "sector": "Utilities",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "TLT",
        "name": "iShares 20+ Year Treasury Bond ETF",
        "sector": "Fixed Income",
        "industry": "ETF",
        "country": "US",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "GLD",
        "name": "SPDR Gold Shares",
        "sector": "Commodities",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "USO",
        "name": "United States Oil Fund",
        "sector": "Commodities",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "EEM",
        "name": "iShares MSCI Emerging Markets ETF",
        "sector": "International",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "FXI",
        "name": "iShares China Large-Cap ETF",
        "sector": "International",
        "industry": "ETF",
        "country": "US",
        "exchange": "NYSE",
    },
    {
        "ticker": "META",
        "name": "Meta Platforms Inc.",
        "sector": "Technology",
        "industry": "Internet Content & Information",
        "country": "US",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "GOOGL",
        "name": "Alphabet Inc.",
        "sector": "Technology",
        "industry": "Internet Content & Information",
        "country": "US",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "AMZN",
        "name": "Amazon.com Inc.",
        "sector": "Technology",
        "industry": "Internet Retail",
        "country": "US",
        "exchange": "NASDAQ",
    },
]


class BootstrapService:
    """One-time first-run data population."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.client = YahooFinanceClient()

    async def run(self, *, skip_prices: bool = False, skip_outcomes: bool = False) -> dict:
        """Execute the full bootstrap sequence.

        Args:
            skip_prices: Skip OHLCV backfill (useful if already done).
            skip_outcomes: Skip landmark event outcome computation.

        Returns:
            A summary dict with counts for each phase.
        """
        summary = {}

        # Phase 1: Register stocks
        logger.info("=== Phase 1: Registering stocks ===")
        stock_count = await self._register_stocks()
        summary["stocks_registered"] = stock_count

        # Phase 2: Backfill OHLCV
        if not skip_prices:
            logger.info("=== Phase 2: Backfilling OHLCV (this may take several minutes) ===")
            backfill = PriceBackfillService(self.session, self.client)
            price_results = await backfill.backfill(INITIAL_TICKERS, start="2008-01-01")
            summary["ohlcv_backfill"] = price_results
        else:
            logger.info("=== Phase 2: OHLCV backfill skipped ===")
            summary["ohlcv_backfill"] = "skipped"

        # Phase 3: Compute landmark event outcomes
        if not skip_outcomes:
            logger.info("=== Phase 3: Computing landmark event outcomes ===")
            collector = HistoricalOutcomeCollector(self.session, self.client)
            outcome_results = await collector.collect_all()
            summary["landmark_outcomes"] = outcome_results
        else:
            logger.info("=== Phase 3: Landmark outcomes skipped ===")
            summary["landmark_outcomes"] = "skipped"

        logger.info(f"=== Bootstrap complete === Summary: {summary}")
        return summary

    async def _register_stocks(self) -> int:
        """Insert seed stock records into the stocks table."""
        count = 0
        for info in SEED_STOCK_INFO:
            try:
                stmt = text("""
                    INSERT INTO stocks (ticker, name, sector, industry, country, exchange)
                    VALUES (:ticker, :name, :sector, :industry, :country, :exchange)
                    ON CONFLICT (ticker) DO UPDATE SET
                        name = EXCLUDED.name,
                        sector = EXCLUDED.sector,
                        industry = EXCLUDED.industry,
                        country = EXCLUDED.country,
                        exchange = EXCLUDED.exchange
                """)
                await self.session.execute(stmt, info)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register {info['ticker']}: {e}")

        await self.session.commit()
        logger.info(f"Registered {count} stocks")
        return count
