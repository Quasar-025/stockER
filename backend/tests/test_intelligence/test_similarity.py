"""Tests for the Hybrid Similarity Engine."""

from datetime import UTC, datetime

import pytest

from app.intelligence.ontology import EventCategory, EventOntologySchema
from app.intelligence.regime import MarketRegime
from app.intelligence.similarity import (
    HybridSimilarityEngine,
    SimilarityWeights,
)


def _make_event(**overrides) -> EventOntologySchema:
    """Factory helper for creating test events."""
    defaults = {
        "title": "Test Event",
        "description": "Test description",
        "source_url": "https://example.com/test",
        "published_at": datetime(2024, 1, 1, tzinfo=UTC),
        "category": EventCategory.INTEREST_RATE_CHANGE,
        "severity_score": 0.5,
        "affected_tickers": ["AAPL"],
        "affected_sectors": ["Technology"],
        "affected_countries": ["USA"],
    }
    defaults.update(overrides)
    return EventOntologySchema(**defaults)


class TestSimilarityWeights:
    """Tests for weight validation."""

    def test_default_weights_sum_to_one(self):
        w = SimilarityWeights()
        total = sum(w.__dict__.values())
        assert abs(total - 1.0) < 0.01

    def test_invalid_weights_raise_error(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            SimilarityWeights(semantic=0.5, sector=0.5, geographic=0.5)


class TestJaccardSimilarity:
    """Tests for Jaccard similarity computation."""

    def test_identical_sets(self):
        score = HybridSimilarityEngine._jaccard(["Tech", "Finance"], ["Tech", "Finance"])
        assert score == 1.0

    def test_disjoint_sets(self):
        score = HybridSimilarityEngine._jaccard(["Tech"], ["Finance"])
        assert score == 0.0

    def test_partial_overlap(self):
        score = HybridSimilarityEngine._jaccard(
            ["Tech", "Finance"], ["Tech", "Healthcare"]
        )
        assert score == pytest.approx(1 / 3, abs=0.01)

    def test_both_empty(self):
        score = HybridSimilarityEngine._jaccard([], [])
        assert score == 1.0

    def test_one_empty(self):
        score = HybridSimilarityEngine._jaccard(["Tech"], [])
        assert score == 0.0

    def test_case_insensitive(self):
        score = HybridSimilarityEngine._jaccard(["TECH"], ["tech"])
        assert score == 1.0


class TestRegimeSimilarity:
    """Tests for regime matching."""

    def test_exact_match(self):
        score = HybridSimilarityEngine._regime_similarity(
            MarketRegime.BULL_LOW_VOL, MarketRegime.BULL_LOW_VOL
        )
        assert score == 1.0

    def test_partial_bull_match(self):
        score = HybridSimilarityEngine._regime_similarity(
            MarketRegime.BULL_LOW_VOL, MarketRegime.BULL_HIGH_VOL
        )
        assert score == 0.7

    def test_partial_bear_match(self):
        score = HybridSimilarityEngine._regime_similarity(
            MarketRegime.BEAR_LOW_VOL, MarketRegime.CRISIS
        )
        assert score == 0.7

    def test_bull_vs_bear_no_match(self):
        score = HybridSimilarityEngine._regime_similarity(
            MarketRegime.BULL_LOW_VOL, MarketRegime.BEAR_HIGH_VOL
        )
        assert score == 0.0


class TestVolatilitySimilarity:
    """Tests for volatility similarity."""

    def test_same_volatility(self):
        score = HybridSimilarityEngine._volatility_similarity(0.15, 0.15)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_different_volatility(self):
        score = HybridSimilarityEngine._volatility_similarity(0.10, 0.40)
        assert score < 0.5  # Large diff → low similarity

    def test_both_zero(self):
        score = HybridSimilarityEngine._volatility_similarity(0.0, 0.0)
        assert score == 1.0


class TestHybridSimilarity:
    """Integration tests for the full hybrid scoring."""

    def setup_method(self):
        self.engine = HybridSimilarityEngine()

    def test_identical_events_high_score(self):
        """Two identical events should score very high."""
        event = _make_event()
        breakdown = self.engine.compute_similarity(
            query=event,
            candidate=event,
            semantic_score=0.95,
            query_regime=MarketRegime.BULL_LOW_VOL,
            candidate_regime=MarketRegime.BULL_LOW_VOL,
            query_volatility=0.15,
            candidate_volatility=0.15,
        )
        assert breakdown.overall_score > 0.85

    def test_completely_different_events_low_score(self):
        """Two unrelated events should score low."""
        query = _make_event(
            affected_sectors=["Technology"],
            affected_countries=["USA"],
        )
        candidate = _make_event(
            affected_sectors=["Energy"],
            affected_countries=["Saudi Arabia"],
        )
        breakdown = self.engine.compute_similarity(
            query=query,
            candidate=candidate,
            semantic_score=0.1,
            query_regime=MarketRegime.BULL_LOW_VOL,
            candidate_regime=MarketRegime.BEAR_HIGH_VOL,
            query_volatility=0.10,
            candidate_volatility=0.50,
        )
        assert breakdown.overall_score < 0.3

    def test_rank_candidates(self):
        """Test that ranking returns sorted results."""
        query = _make_event()

        good_match = _make_event(
            source_url="https://example.com/good",
            affected_sectors=["Technology"],
        )
        bad_match = _make_event(
            source_url="https://example.com/bad",
            affected_sectors=["Energy"],
            affected_countries=["Japan"],
        )

        candidates = [
            (bad_match, 0.3, MarketRegime.BEAR_HIGH_VOL, 0.40),
            (good_match, 0.9, MarketRegime.BULL_LOW_VOL, 0.15),
        ]

        results = self.engine.rank_candidates(
            query=query,
            candidates=candidates,
            query_regime=MarketRegime.BULL_LOW_VOL,
            query_volatility=0.15,
            top_k=2,
        )

        assert len(results) == 2
        # Good match should be first
        assert results[0][1].overall_score > results[1][1].overall_score

    def test_top_k_limiting(self):
        """Test that top_k limits the results."""
        query = _make_event()
        candidates = [
            (_make_event(source_url=f"https://example.com/{i}"), 0.5, MarketRegime.SIDEWAYS, 0.2)
            for i in range(20)
        ]

        results = self.engine.rank_candidates(
            query=query,
            candidates=candidates,
            query_regime=MarketRegime.SIDEWAYS,
            query_volatility=0.2,
            top_k=5,
        )
        assert len(results) == 5

    def test_breakdown_fields_populated(self):
        """Test that all breakdown fields exist and are bounded."""
        event = _make_event()
        breakdown = self.engine.compute_similarity(
            query=event,
            candidate=event,
            semantic_score=0.8,
            query_regime=MarketRegime.BULL_LOW_VOL,
            candidate_regime=MarketRegime.BULL_LOW_VOL,
        )

        assert 0 <= breakdown.overall_score <= 1
        assert 0 <= breakdown.semantic_score <= 1
        assert 0 <= breakdown.sector_score <= 1
        assert 0 <= breakdown.geographic_score <= 1
        assert 0 <= breakdown.regime_score <= 1
        assert 0 <= breakdown.volatility_score <= 1
