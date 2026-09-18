"""Yahoo Finance price data client via yfinance.

Free, no API key required.  Provides daily OHLCV for any ticker going
back decades — the primary source for the OHLCV hypertable, market
benchmark returns, sector ETF returns, and VIX history.
"""

import logging
from datetime import UTC, date, datetime
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

# Sector → representative ETF (SPDR / Select Sector)
SECTOR_ETFS: dict[str, str] = {
    "Technology": "XLK",
    "Semiconductors": "XLK",
    "Software": "XLK",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Health Care": "XLV",
    "Energy": "XLE",
    "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY",
    "Consumer Defensive": "XLP",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Communication Services": "XLC",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
    "Materials": "XLB",
    "Utilities": "XLU",
}

MARKET_BENCHMARK = "SPY"
VIX_TICKER = "^VIX"


class YahooFinanceClient:
    """Download daily OHLCV data from Yahoo Finance."""

    def download_ohlcv(
        self,
        tickers: str | list[str],
        start: str | date,
        end: str | date | None = None,
    ) -> list[dict[str, Any]]:
        """Download daily OHLCV for one or more tickers.

        Returns a flat list of row dicts with keys matching the ``OHLCV``
        model: ``time``, ``ticker``, ``open``, ``high``, ``low``,
        ``close``, ``volume``.
        """
        if isinstance(tickers, str):
            tickers = [tickers]

        end_str = str(end) if end else str(date.today())
        start_str = str(start)

        rows: list[dict[str, Any]] = []

        for ticker in tickers:
            try:
                df = yf.download(
                    ticker,
                    start=start_str,
                    end=end_str,
                    auto_adjust=True,
                    progress=False,
                )

                if df.empty:
                    logger.warning(f"No OHLCV data returned for {ticker}")
                    continue

                # yfinance may return MultiIndex columns for single ticker
                # Flatten if needed
                if hasattr(df.columns, "levels") and len(df.columns.levels) > 1:
                    df.columns = df.columns.get_level_values(0)

                for idx, row in df.iterrows():
                    ts = idx
                    if hasattr(ts, "to_pydatetime"):
                        ts = ts.to_pydatetime()
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=UTC)

                    vol = row.get("Volume", 0)
                    rows.append(
                        {
                            "time": ts,
                            "ticker": ticker,
                            "open": float(row["Open"]),
                            "high": float(row["High"]),
                            "low": float(row["Low"]),
                            "close": float(row["Close"]),
                            "volume": int(vol) if vol == vol else 0,  # NaN guard
                        }
                    )

                logger.info(f"Downloaded {len(rows)} OHLCV rows for {ticker}")

            except Exception as e:
                logger.error(f"Failed to download OHLCV for {ticker}: {e}")

        return rows

    def download_close_series(
        self,
        ticker: str,
        start: str | date,
        end: str | date | None = None,
    ) -> dict[date, float]:
        """Download daily close prices as a date→float mapping.

        Useful for quick return computations without full OHLCV overhead.
        """
        rows = self.download_ohlcv(ticker, start, end)
        result: dict[date, float] = {}
        for row in rows:
            dt = row["time"]
            d = dt.date() if isinstance(dt, datetime) else dt
            result[d] = row["close"]
        return result

    def download_vix(
        self,
        start: str | date,
        end: str | date | None = None,
    ) -> dict[date, float]:
        """Download VIX close values."""
        return self.download_close_series(VIX_TICKER, start, end)

    def sector_etf_for(self, sector: str) -> str | None:
        """Resolve a sector name to its representative ETF ticker."""
        return SECTOR_ETFS.get(sector)

    def get_company_name(self, ticker: str) -> str | None:
        """Fetch shortName from yfinance, using an in-memory cache."""
        import functools

        # Need to attach cache to the function, not method, to avoid caching `self`
        if not hasattr(self.__class__, "_name_cache"):

            @functools.lru_cache(maxsize=1024)
            def _fetch(t: str):
                try:
                    import yfinance as yf

                    tk = yf.Ticker(t)
                    return tk.info.get("shortName") or tk.info.get("longName")
                except Exception as e:
                    logger.warning(f"Failed to fetch company name for {t}: {e}")
                    return None

            self.__class__._name_cache = _fetch

        return self.__class__._name_cache(ticker)
