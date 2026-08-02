"""Tests for SQLAlchemy core models."""

from datetime import datetime, timezone

from app.models.core import Stock, OHLCV


def test_stock_model_creation():
    """Test that Stock model can be instantiated with required fields."""
    stock = Stock(
        ticker="AAPL",
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        country="USA",
        exchange="NASDAQ",
    )
    
    assert stock.ticker == "AAPL"
    assert stock.name == "Apple Inc."
    assert stock.sector == "Technology"


def test_ohlcv_model_creation():
    """Test that OHLCV model can be instantiated with required fields."""
    now = datetime.now(timezone.utc)
    candle = OHLCV(
        time=now,
        ticker="AAPL",
        open=150.0,
        high=155.0,
        low=149.0,
        close=154.0,
        volume=1000000,
    )
    
    assert candle.ticker == "AAPL"
    assert candle.time == now
    assert candle.close == 154.0
    assert candle.volume == 1000000
