"""Tests for the Market Impact Engine."""

import pytest
from datetime import datetime, timezone

from app.intelligence.impact import MarketImpactEngine, ForecastResult
from app.intelligence.similarity import SimilarityBreakdown, SimilarityWeights
from app.intelligence.ontology import EventOntologySchema, EventCategory
from app.intelligence.regime import MarketRegime


def _make_event(**overrides) -> EventOntologySchema:
    defaults = {
        "title": "Test Event",
        "description": "Test",
        "source_url": "https://example.com/test",
        "published_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "category": EventCategory.INTEREST_RATE_CHANGE,
        "severity_score": 0.5,
        "affected_tickers": ["AAPL"],
        "affected_sectors": ["Technology"],
        "affected_countries": ["USA"],
    }
    defaults.update(overrides)
    return EventOntologySchema(**defaults)


def _make_breakdown(overall: float) -> SimilarityBreakdown:
    return SimilarityBreakdown(
        overall_score=overall,
        semantic_score=overall,
        sector_score=overall,
        geographic_score=overall,
        regime_score=overall,
        volatility_score=overall,
    )


class TestMarketImpactEngine:
    def setup_method(self):
        self.engine = MarketImpactEngine()

    def test_no_similar_events_returns_zero(self):
        """No similar events → zero impact, zero confidence."""
        result = self.engine.compute_forecast(
            event=_make_event(),
            ticker="AAPL",
            similar_events=[],
            current_regime=MarketRegime.BULL_LOW_VOL,
        )
        assert result.predicted_impact == 0.0
        assert result.confidence_score == 0.0

    def test_single_similar_event(self):
        """Single similar event → impact matches that event's history."""
        event = _make_event()
        hist_event = _make_event(source_url="https://example.com/hist")
        breakdown = _make_breakdown(0.9)

        result = self.engine.compute_forecast(
            event=event,
            ticker="AAPL",
            similar_events=[(hist_event, breakdown, -0.05)],
            current_regime=MarketRegime.BULL_LOW_VOL,
        )
        assert result.predicted_impact == pytest.approx(-0.05, abs=0.01)
        assert result.confidence_score > 0

    def test_weighted_average_multiple_events(self):
        """Multiple events → weighted average by similarity."""
        event = _make_event()

        similar = [
            (_make_event(source_url="https://a.com/1"), _make_breakdown(0.9), -0.10),
            (_make_event(source_url="https://a.com/2"), _make_breakdown(0.1), 0.10),
        ]

        result = self.engine.compute_forecast(
            event=event,
            ticker="AAPL",
            similar_events=similar,
            current_regime=MarketRegime.BEAR_HIGH_VOL,
        )
        # Weighted toward the -0.10 event (0.9 weight)
        assert result.predicted_impact < 0

    def test_confidence_increases_with_more_events(self):
        """More similar events should increase confidence."""
        event = _make_event()

        one_event = [(_make_event(source_url="https://a.com/1"), _make_breakdown(0.8), -0.05)]
        five_events = [
            (_make_event(source_url=f"https://a.com/{i}"), _make_breakdown(0.8), -0.05)
            for i in range(5)
        ]

        result_one = self.engine.compute_forecast(
            event=event, ticker="AAPL", similar_events=one_event,
            current_regime=MarketRegime.BULL_LOW_VOL,
        )
        result_five = self.engine.compute_forecast(
            event=event, ticker="AAPL", similar_events=five_events,
            current_regime=MarketRegime.BULL_LOW_VOL,
        )
        assert result_five.confidence_score > result_one.confidence_score

    def test_causal_chain_passed_through(self):
        """Causal chain from Neo4j should be included in forecast."""
        chain = ["Taiwan Earthquake", "TSMC Shutdown", "Apple Supply Shortage"]
        result = self.engine.compute_forecast(
            event=_make_event(),
            ticker="AAPL",
            similar_events=[],
            current_regime=MarketRegime.BULL_LOW_VOL,
            causal_chain=chain,
        )
        assert result.causal_chain == chain

    def test_forecast_result_fields(self):
        """All fields should be populated."""
        result = self.engine.compute_forecast(
            event=_make_event(),
            ticker="NVDA",
            similar_events=[
                (_make_event(source_url="https://a.com/1"), _make_breakdown(0.7), -0.03)
            ],
            current_regime=MarketRegime.BULL_HIGH_VOL,
        )
        assert result.ticker == "NVDA"
        assert result.market_regime == MarketRegime.BULL_HIGH_VOL
        assert result.time_horizon_days == 30
        assert len(result.similar_events) == 1
        assert result.created_at is not None
