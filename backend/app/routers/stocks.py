"""Stocks router — list, retrieve, and trigger price refreshes."""

from typing import Any
import logging
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("")
async def list_stocks(  # type: ignore[no-untyped-def]
    sector: str | None = Query(None, description="Filter by sector"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """List registered stocks with optional sector filter."""
    params: dict = {"limit": limit, "offset": offset}

    where_clause = ""
    if sector:
        where_clause = "WHERE sector = :sector"
        params["sector"] = sector

    stmt = text(f"""
        SELECT ticker, name, sector, industry, country, exchange, last_updated
        FROM stocks
        {where_clause}
        ORDER BY ticker
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(stmt, params)
    rows = result.mappings().all()

    return {
        "stocks": [dict(row) for row in rows],
        "count": len(rows),
        "offset": offset,
        "limit": limit,
    }


@router.get("/{ticker}")
async def get_stock(ticker: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:  # noqa: B008
    """Retrieve detailed stock information including latest OHLCV."""
    ticker = ticker.upper()

    # Fetch stock profile
    stmt = text("""
        SELECT ticker, name, sector, industry, country, exchange,
               beta, short_interest, short_ratio, volume_avg_10d,
               high_52w, low_52w, last_updated
        FROM stocks
        WHERE ticker = :ticker
    """)
    result = await db.execute(stmt, {"ticker": ticker})
    stock = result.mappings().first()

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Fetch latest OHLCV row
    ohlcv_stmt = text("""
        SELECT time, open, high, low, close, volume
        FROM ohlcv
        WHERE ticker = :ticker
        ORDER BY time DESC
        LIMIT 1
    """)
    ohlcv_result = await db.execute(ohlcv_stmt, {"ticker": ticker})
    latest_ohlcv = ohlcv_result.mappings().first()

    return {
        "stock": dict(stock),
        "latest_price": dict(latest_ohlcv) if latest_ohlcv else None,
    }


@router.get("/{ticker}/prices")
async def get_stock_prices(  # type: ignore[no-untyped-def]
    ticker: str,
    days: int = Query(30, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Retrieve OHLCV time-series data for a ticker."""
    ticker = ticker.upper()

    start_date = datetime.now(UTC) - timedelta(days=days)

    stmt = text("""
        SELECT time, open, high, low, close, volume
        FROM ohlcv
        WHERE ticker = :ticker AND time >= :start_date
        ORDER BY time ASC
    """)
    result = await db.execute(stmt, {"ticker": ticker, "start_date": start_date})
    rows = result.mappings().all()

    return {
        "ticker": ticker,
        "prices": [dict(row) for row in rows],
        "days": days,
    }


@router.post("/{ticker}/refresh")
async def refresh_stock_prices(  # type: ignore[no-untyped-def]
    ticker: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Trigger an immediate price data refresh for a ticker via yfinance."""
    ticker = ticker.upper()

    from app.ingestion.price_backfill import PriceBackfillService
    from app.ingestion.yahoo_finance import YahooFinanceClient

    try:
        start_date = date.today() - timedelta(days=days)
        client = YahooFinanceClient()
        backfill = PriceBackfillService(session=db, client=client)

        results = await backfill.backfill([ticker], start=start_date, include_benchmark=False)
        rows_inserted = results.get(ticker, 0)

        return {
            "status": "success",
            "ticker": ticker,
            "rows_upserted": rows_inserted,
        }
    except Exception as e:
        logger.error(f"Price refresh failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
