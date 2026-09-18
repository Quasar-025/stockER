"""Tests for Event and Forecast models."""

import uuid
from datetime import UTC, datetime

from app.models.events import EventObject
from app.models.forecast import Forecast


def test_event_object_creation():
    """Test that EventObject model can be instantiated."""
    event_id = uuid.uuid4()
    now = datetime.now(UTC)

    event = EventObject(
        id=event_id,
        title="Major earthquake hits Taiwan, disrupting semiconductor supply chains",
        description="A 7.4 magnitude earthquake struck Taiwan's eastern coast today...",
        source_url="https://example.com/news/earthquake-taiwan",
        published_at=now,
        category="SUPPLY_CHAIN_DISRUPTION",
        severity_score=0.85,
        affected_tickers=["TSM", "AAPL", "NVDA"],
        affected_sectors=["Semiconductors", "Consumer Electronics"],
        affected_countries=["Taiwan", "USA"],
    )

    assert event.id == event_id
    assert event.category == "SUPPLY_CHAIN_DISRUPTION"
    assert "TSM" in event.affected_tickers
    assert event.severity_score == 0.85


def test_forecast_creation():
    """Test that Forecast model can be instantiated."""
    forecast_id = uuid.uuid4()
    event_id = uuid.uuid4()

    forecast = Forecast(
        id=forecast_id,
        event_id=event_id,
        ticker="AAPL",
        predicted_impact=-0.045,
        confidence_score=0.72,
        time_horizon_days=30,
        similar_historical_events=[{"id": "some_uuid", "similarity": 0.88}],
        causal_chain=["Taiwan Earthquake", "TSMC Factory Shutdown", "Apple Supply Shortage"],
        market_regime="BULL_HIGH_VOLATILITY",
    )

    assert forecast.ticker == "AAPL"
    assert forecast.predicted_impact == -0.045
    assert forecast.confidence_score == 0.72
    assert "TSMC Factory Shutdown" in forecast.causal_chain
