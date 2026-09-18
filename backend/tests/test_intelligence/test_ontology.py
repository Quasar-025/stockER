"""Tests for Event Ontology schema."""

from datetime import UTC, datetime

import pytest

from app.intelligence.ontology import (
    CATEGORY_SCOPE,
    EventCategory,
    EventOntologySchema,
    SeverityLevel,
)


class TestEventCategory:
    """Tests for the EventCategory enum."""

    def test_all_categories_are_strings(self):
        """Every category value should be a plain uppercase string."""
        for cat in EventCategory:
            assert cat.value == cat.value.upper()
            assert isinstance(cat.value, str)

    def test_category_count(self):
        """Verify we have a comprehensive set of categories."""
        assert len(EventCategory) >= 30

    def test_core_categories_exist(self):
        """Verify essential categories are present."""
        assert EventCategory.INTEREST_RATE_CHANGE
        assert EventCategory.SUPPLY_CHAIN_DISRUPTION
        assert EventCategory.EARNINGS_SURPRISE
        assert EventCategory.MERGER_ACQUISITION
        assert EventCategory.NATURAL_DISASTER
        assert EventCategory.MARKET_CRASH


class TestSeverityLevel:
    """Tests for severity score to level mapping."""

    def test_low_severity(self):
        assert SeverityLevel.from_score(0.0) == SeverityLevel.LOW
        assert SeverityLevel.from_score(0.29) == SeverityLevel.LOW

    def test_medium_severity(self):
        assert SeverityLevel.from_score(0.3) == SeverityLevel.MEDIUM
        assert SeverityLevel.from_score(0.59) == SeverityLevel.MEDIUM

    def test_high_severity(self):
        assert SeverityLevel.from_score(0.6) == SeverityLevel.HIGH
        assert SeverityLevel.from_score(0.79) == SeverityLevel.HIGH

    def test_critical_severity(self):
        assert SeverityLevel.from_score(0.8) == SeverityLevel.CRITICAL
        assert SeverityLevel.from_score(1.0) == SeverityLevel.CRITICAL


class TestEventOntologySchema:
    """Tests for the EventOntologySchema Pydantic model."""

    def _make_event(self, **overrides) -> EventOntologySchema:
        """Factory helper for creating test events."""
        defaults = {
            "title": "Fed raises rates by 25 bps",
            "description": "The Federal Reserve raised interest rates...",
            "source_url": "https://example.com/fed-rate-hike",
            "published_at": datetime(2024, 3, 20, 14, 0, tzinfo=UTC),
            "category": EventCategory.INTEREST_RATE_CHANGE,
            "severity_score": 0.75,
            "affected_tickers": ["SPY", "QQQ"],
            "affected_sectors": ["Financials", "Technology"],
            "affected_countries": ["USA"],
        }
        defaults.update(overrides)
        return EventOntologySchema(**defaults)

    def test_basic_creation(self):
        event = self._make_event()
        assert event.title == "Fed raises rates by 25 bps"
        assert event.category == EventCategory.INTEREST_RATE_CHANGE

    def test_severity_level_property(self):
        event = self._make_event(severity_score=0.75)
        assert event.severity_level == SeverityLevel.HIGH

    def test_is_macro_true(self):
        event = self._make_event(category=EventCategory.INTEREST_RATE_CHANGE)
        assert event.is_macro is True
        assert event.is_geopolitical is False

    def test_is_geopolitical_true(self):
        event = self._make_event(category=EventCategory.TRADE_WAR)
        assert event.is_geopolitical is True
        assert event.is_macro is False

    def test_severity_score_validation(self):
        """Score must be between 0 and 1."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            self._make_event(severity_score=1.5)

        with pytest.raises(Exception):
            self._make_event(severity_score=-0.1)

    def test_default_empty_lists(self):
        event = self._make_event(
            affected_tickers=[],
            affected_sectors=[],
            affected_countries=[],
        )
        assert event.affected_tickers == []
        assert event.supply_chain_impact == []

    def test_supply_chain_impact(self):
        event = self._make_event(
            category=EventCategory.SUPPLY_CHAIN_DISRUPTION,
            supply_chain_impact=["TSMC → Apple", "Apple → Cloud Providers"],
        )
        assert len(event.supply_chain_impact) == 2


class TestCategoryScope:
    """Tests for the CATEGORY_SCOPE mapping."""

    def test_macro_events_are_market_wide(self):
        assert CATEGORY_SCOPE[EventCategory.INTEREST_RATE_CHANGE] == "market_wide"
        assert CATEGORY_SCOPE[EventCategory.PANDEMIC] == "market_wide"

    def test_company_events_are_single_stock(self):
        assert CATEGORY_SCOPE[EventCategory.EARNINGS_SURPRISE] == "single_stock"
        assert CATEGORY_SCOPE[EventCategory.CEO_CHANGE] == "single_stock"

    def test_supply_chain_is_sector(self):
        assert CATEGORY_SCOPE[EventCategory.SUPPLY_CHAIN_DISRUPTION] == "sector"
