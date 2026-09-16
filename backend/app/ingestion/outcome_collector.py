"""Compute verified price outcomes for the 60 landmark events.

For each event in ``landmark_events.json``, this module downloads OHLCV
data via yfinance and computes multi-horizon returns, market/sector
factor returns, volatility changes, volume changes, recovery time, VIX
at event, and market regime at event.

The results are persisted as ``CanonicalEvent`` + ``HistoricalEventOutcome``
records — the empirical calibration data the intelligence pipeline requires.
"""

import json
import logging
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.yahoo_finance import MARKET_BENCHMARK, SECTOR_ETFS, YahooFinanceClient
from app.intelligence.regime import MarketRegimeDetector

logger = logging.getLogger(__name__)

# Path to the landmark events JSON
LANDMARK_EVENTS_PATH = Path(__file__).resolve().parents[2] / "data" / "landmark_events.json"

# Category → (representative tickers, primary sector)
# Covers the key tickers that are most meaningfully affected per category
CATEGORY_TICKER_MAP: dict[str, tuple[list[str], str]] = {
    "BANKRUPTCY": (["SPY", "XLF"], "Financials"),
    "REGULATORY_ACTION": (["SPY", "QQQ"], "Technology"),
    "FLASH_CRASH": (["SPY", "QQQ", "DIA"], "Technology"),
    "NATURAL_DISASTER": (["SPY", "XLE", "XLI"], "Industrials"),
    "SUPPLY_CHAIN_DISRUPTION": (["TSM", "NVDA", "AAPL", "XLK", "SPY"], "Technology"),
    "MONETARY_POLICY": (["SPY", "QQQ", "TLT", "XLF"], "Financials"),
    "COMMODITY_SHOCK": (["XLE", "USO", "SPY"], "Energy"),
    "CURRENCY_CRISIS": (["SPY", "EEM", "FXI"], "Financials"),
    "MARKET_CRASH": (["SPY", "QQQ", "DIA", "IWM"], "Technology"),
    "ELECTION": (["SPY", "QQQ", "DIA"], "Technology"),
    "TRADE_WAR": (["SPY", "QQQ", "FXI", "EEM"], "Technology"),
    "ENERGY_CRISIS": (["XLE", "USO", "SPY"], "Energy"),
    "LIQUIDITY_CRISIS": (["XLF", "SPY", "TLT"], "Financials"),
    "PANDEMIC": (["SPY", "QQQ", "XLV", "XLE"], "Healthcare"),
    "SHORT_SQUEEZE": (["SPY", "IWM"], "Financials"),
    "CLIMATE_EVENT": (["TSM", "XLK", "SPY"], "Technology"),
    "TECH_REGULATION": (["QQQ", "META", "GOOGL", "AMZN"], "Technology"),
    "MILITARY_CONFLICT": (["SPY", "XLE", "GLD", "XLI"], "Energy"),
    "INTEREST_RATE_CHANGE": (["SPY", "TLT", "XLF", "QQQ"], "Financials"),
    "CYBERSECURITY_BREACH": (["QQQ", "XLK", "SPY"], "Technology"),
    "EARNINGS_MISS": (["SPY", "QQQ"], "Technology"),
    "POLITICAL_INSTABILITY": (["SPY", "QQQ", "EEM"], "Technology"),
    "OTHER": (["SPY"], "Technology"),
}

HORIZONS = [1, 3, 7, 14, 30, 90]


class HistoricalOutcomeCollector:
    """Compute and store multi-horizon outcomes for landmark events."""

    def __init__(
        self,
        session: AsyncSession,
        client: YahooFinanceClient | None = None,
    ) -> None:
        self.session = session
        self.client = client or YahooFinanceClient()
        self.regime_detector = MarketRegimeDetector()

    async def collect_all(self) -> dict[str, Any]:
        """Process all landmark events and return a summary."""
        events = self._load_landmark_events()
        logger.info(f"Processing {len(events)} landmark events")

        summary: dict[str, Any] = {"processed": 0, "skipped": 0, "errors": 0, "details": {}}

        for event in events:
            try:
                event_id = event["id"]
                event_date_str = event["event_date"]
                event_date = datetime.strptime(event_date_str, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                category = event["category"]
                title = event["title"]

                # Resolve tickers and sector for this category
                tickers, sector = CATEGORY_TICKER_MAP.get(
                    category, (["SPY"], "Technology")
                )

                # Download price data (event_date - 90d to event_date + 120d)
                data_start = (event_date - timedelta(days=120)).date()
                data_end = (event_date + timedelta(days=150)).date()

                # Cap end date at today
                today = date.today()
                if data_end > today:
                    data_end = today

                # Skip events that don't have enough post-event data yet
                min_end = (event_date + timedelta(days=2)).date()
                if min_end > today:
                    logger.info(f"Skipping {event_id}: event too recent for outcomes")
                    summary["skipped"] += 1
                    continue

                # Download all needed price data
                all_tickers_needed = list(set(tickers + [MARKET_BENCHMARK]))
                sector_etf = self.client.sector_etf_for(sector)
                if sector_etf and sector_etf not in all_tickers_needed:
                    all_tickers_needed.append(sector_etf)

                close_data: dict[str, dict[date, float]] = {}
                for ticker in all_tickers_needed:
                    close_data[ticker] = self.client.download_close_series(
                        ticker, data_start, data_end
                    )

                # Download VIX
                vix_data = self.client.download_vix(data_start, data_end)

                # Compute market regime from SPY returns
                spy_closes = close_data.get(MARKET_BENCHMARK, {})
                regime = self._compute_regime(spy_closes, event_date.date())

                # Get VIX at event
                vix_at_event = self._get_value_at_date(vix_data, event_date.date())

                # Create canonical event
                canonical_id = await self._upsert_canonical_event(
                    event_id=event_id,
                    title=title,
                    category=category,
                    event_date=event_date,
                    regime=regime,
                    vix=vix_at_event,
                    tickers=tickers,
                    sector=sector,
                )

                # Compute outcomes for each affected ticker
                outcomes_created = 0
                for ticker in tickers:
                    ticker_closes = close_data.get(ticker, {})
                    spy_c = close_data.get(MARKET_BENCHMARK, {})
                    sector_c = close_data.get(sector_etf, {}) if sector_etf else {}

                    outcome = self._compute_outcome(
                        ticker_closes, spy_c, sector_c,
                        event_date.date(), canonical_id,
                        ticker,
                    )
                    if outcome:
                        await self._upsert_outcome(outcome)
                        outcomes_created += 1

                summary["processed"] += 1
                summary["details"][event_id] = {
                    "title": title,
                    "outcomes": outcomes_created,
                    "regime": regime,
                }
                logger.info(
                    f"Processed {event_id}: {title} → {outcomes_created} outcomes"
                )

            except Exception as e:
                logger.error(f"Error processing event {event.get('id', '?')}: {e}")
                summary["errors"] += 1

        return summary

    def _load_landmark_events(self) -> list[dict[str, Any]]:
        """Load landmark events from the JSON file."""
        with open(LANDMARK_EVENTS_PATH) as f:
            return json.load(f)

    def _compute_regime(self, spy_closes: dict[date, float], event_date: date) -> str:
        """Compute market regime from SPY returns before the event."""
        sorted_dates = sorted(d for d in spy_closes if d <= event_date)
        if len(sorted_dates) < 10:
            return "SIDEWAYS"

        # Compute daily log returns
        prices = [spy_closes[d] for d in sorted_dates[-70:]]
        if len(prices) < 5:
            return "SIDEWAYS"

        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0:
                returns.append(math.log(prices[i] / prices[i - 1]))

        result = self.regime_detector.detect(returns)
        return result.regime.value

    def _get_value_at_date(
        self, data: dict[date, float], target: date, max_lookback: int = 5
    ) -> float | None:
        """Get value at target date, or nearest prior date within lookback."""
        for offset in range(max_lookback + 1):
            d = target - timedelta(days=offset)
            if d in data:
                return data[d]
        return None

    def _compute_return(
        self, closes: dict[date, float], event_date: date, horizon_days: int
    ) -> float | None:
        """Compute return from event_date to event_date + horizon_days."""
        # Find the closest trading day at or before event_date
        base_price = self._get_value_at_date(closes, event_date)
        if base_price is None or base_price <= 0:
            return None

        # Find the closest trading day at or after event_date + horizon
        target_date = event_date + timedelta(days=horizon_days)
        # Look forward up to 5 days for a trading day
        for offset in range(6):
            d = target_date + timedelta(days=offset)
            if d in closes:
                return (closes[d] / base_price) - 1.0
        return None

    def _compute_outcome(
        self,
        ticker_closes: dict[date, float],
        spy_closes: dict[date, float],
        sector_closes: dict[date, float],
        event_date: date,
        canonical_event_id: uuid.UUID,
        ticker: str,
    ) -> dict[str, Any] | None:
        """Compute the full outcome record for one ticker."""
        if not ticker_closes:
            return None

        # Multi-horizon returns
        returns: dict[str, float | None] = {}
        for h in HORIZONS:
            returns[f"return_{h}d"] = self._compute_return(ticker_closes, event_date, h)

        # Market return (30d horizon as the primary)
        market_return = self._compute_return(spy_closes, event_date, 30)

        # Sector excess return
        sector_return = self._compute_return(sector_closes, event_date, 30)
        sector_excess = None
        if sector_return is not None and market_return is not None:
            sector_excess = sector_return - market_return

        # Volatility change: post-event 30d vol / pre-event 30d vol
        vol_change = self._compute_volatility_change(ticker_closes, event_date)

        # Volume change is not available from close-only data; skip

        # Recovery time
        recovery = self._compute_recovery_days(ticker_closes, event_date)

        # Determine available_at: the latest date for which we have data
        max_date = max(ticker_closes.keys()) if ticker_closes else event_date
        available_at = datetime(max_date.year, max_date.month, max_date.day, tzinfo=timezone.utc)

        return {
            "canonical_event_id": canonical_event_id,
            "ticker": ticker,
            "return_1d": returns.get("return_1d"),
            "return_3d": returns.get("return_3d"),
            "return_7d": returns.get("return_7d"),
            "return_14d": returns.get("return_14d"),
            "return_30d": returns.get("return_30d"),
            "return_90d": returns.get("return_90d"),
            "market_return": market_return,
            "sector_excess_return": sector_excess,
            "volatility_change": vol_change,
            "volume_change": None,
            "recovery_time_days": recovery,
            "available_at": available_at,
            "quality_metadata": {"source": "yfinance", "method": "automated"},
            "is_seeded_demo": False,
        }

    def _compute_volatility_change(
        self, closes: dict[date, float], event_date: date
    ) -> float | None:
        """Compute realized volatility ratio (post/pre event)."""
        sorted_dates = sorted(closes.keys())
        pre_dates = [d for d in sorted_dates if d < event_date]
        post_dates = [d for d in sorted_dates if d > event_date]

        if len(pre_dates) < 10 or len(post_dates) < 10:
            return None

        def _realized_vol(dates: list[date]) -> float:
            prices = [closes[d] for d in dates]
            log_returns = []
            for i in range(1, len(prices)):
                if prices[i - 1] > 0:
                    log_returns.append(math.log(prices[i] / prices[i - 1]))
            if len(log_returns) < 2:
                return 0.0
            mean_r = sum(log_returns) / len(log_returns)
            var = sum((r - mean_r) ** 2 for r in log_returns) / len(log_returns)
            return math.sqrt(var)

        pre_vol = _realized_vol(pre_dates[-30:])
        post_vol = _realized_vol(post_dates[:30])

        if pre_vol < 1e-10:
            return None
        return post_vol / pre_vol

    def _compute_recovery_days(
        self, closes: dict[date, float], event_date: date
    ) -> int | None:
        """Days until close ≥ pre-event close after a decline."""
        pre_close = self._get_value_at_date(closes, event_date)
        if pre_close is None:
            return None

        sorted_dates = sorted(d for d in closes if d > event_date)
        for i, d in enumerate(sorted_dates):
            if closes[d] >= pre_close:
                return i + 1  # 1-indexed trading days

        return None  # Never recovered in available data

    async def _upsert_canonical_event(
        self,
        event_id: str,
        title: str,
        category: str,
        event_date: datetime,
        regime: str,
        vix: float | None,
        tickers: list[str],
        sector: str,
    ) -> uuid.UUID:
        """Create or update a canonical event record."""
        canonical_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"stocker.landmark.{event_id}")

        stmt = text("""
            INSERT INTO canonical_events (
                id, title, description, category, event_date,
                market_regime_at_event, vix_at_event,
                affected_tickers, affected_sectors,
                data_source, bootstrap_status, is_seeded_demo, created_at
            ) VALUES (
                :id, :title, :description, :category, :event_date,
                :regime, :vix,
                :tickers, :sectors,
                :source, :status, false, NOW()
            )
            ON CONFLICT (id) DO UPDATE SET
                market_regime_at_event = EXCLUDED.market_regime_at_event,
                vix_at_event = EXCLUDED.vix_at_event,
                affected_tickers = EXCLUDED.affected_tickers,
                bootstrap_status = EXCLUDED.bootstrap_status
        """)

        await self.session.execute(stmt, {
            "id": canonical_id,
            "title": title,
            "description": title,
            "category": category,
            "event_date": event_date,
            "regime": regime,
            "vix": vix,
            "tickers": json.dumps(tickers),
            "sectors": json.dumps([sector]),
            "source": "landmark_events.json",
            "status": "outcomes_computed",
        })
        await self.session.commit()
        return canonical_id

    async def _upsert_outcome(self, outcome: dict[str, Any]) -> None:
        """Insert or update a historical event outcome."""
        stmt = text("""
            INSERT INTO historical_event_outcomes (
                id, canonical_event_id, ticker,
                return_1d, return_3d, return_7d, return_14d, return_30d, return_90d,
                market_return, sector_excess_return,
                volatility_change, volume_change, recovery_time_days,
                available_at, quality_metadata, is_seeded_demo
            ) VALUES (
                gen_random_uuid(), :canonical_event_id, :ticker,
                :return_1d, :return_3d, :return_7d, :return_14d, :return_30d, :return_90d,
                :market_return, :sector_excess_return,
                :volatility_change, :volume_change, :recovery_time_days,
                :available_at, :quality_metadata, :is_seeded_demo
            )
            ON CONFLICT ON CONSTRAINT uq_outcome_event_ticker DO UPDATE SET
                return_1d = EXCLUDED.return_1d,
                return_3d = EXCLUDED.return_3d,
                return_7d = EXCLUDED.return_7d,
                return_14d = EXCLUDED.return_14d,
                return_30d = EXCLUDED.return_30d,
                return_90d = EXCLUDED.return_90d,
                market_return = EXCLUDED.market_return,
                sector_excess_return = EXCLUDED.sector_excess_return,
                volatility_change = EXCLUDED.volatility_change,
                recovery_time_days = EXCLUDED.recovery_time_days,
                available_at = EXCLUDED.available_at,
                quality_metadata = EXCLUDED.quality_metadata
        """)

        params = dict(outcome)
        params["quality_metadata"] = json.dumps(params["quality_metadata"])
        await self.session.execute(stmt, params)
        await self.session.commit()
