"""Hybrid Similarity Engine — The heart of StockER.

Computes multi-dimensional similarity between events using weighted
dimensions, as specified in the architecture:

  1. Semantic similarity (35%) — embedding cosine distance
  2. Sector overlap    (25%) — Jaccard similarity of affected sectors
  3. Geographic overlap (15%) — Jaccard similarity of affected countries
  4. Regime match      (15%) — same market regime → bonus
  5. Volatility match
  6. Severity, magnitude, and duration proximity
  7. Exposure and supply-chain structural similarity

The LLM never touches this. Pure math.
"""

import logging
from dataclasses import dataclass, field

from app.intelligence.ontology import EventOntologySchema
from app.intelligence.regime import MarketRegime

logger = logging.getLogger(__name__)


@dataclass
class SimilarityWeights:
    """Configurable weights for each similarity dimension."""

    semantic: float = 0.25
    sector: float = 0.16
    geographic: float = 0.10
    regime: float = 0.10
    volatility: float = 0.08
    severity_similarity: float = 0.08
    magnitude_similarity: float = 0.10
    duration_similarity: float = 0.05
    exposure_similarity: float = 0.04
    structural_similarity: float = 0.04

    def __post_init__(self) -> None:
        total = sum(self.__dict__.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


@dataclass
class SimilarityBreakdown:
    """Detailed breakdown of a similarity score."""

    overall_score: float
    semantic_score: float
    sector_score: float
    geographic_score: float
    regime_score: float
    volatility_score: float
    severity_score: float = 0.0
    magnitude_score: float = 0.0
    duration_score: float = 0.0
    exposure_score: float = 0.0
    structural_score: float = 0.0
    weights: SimilarityWeights = field(default_factory=SimilarityWeights)


@dataclass
class SimilarEvent:
    """A historical event found to be similar to the query event."""

    event: EventOntologySchema
    similarity: SimilarityBreakdown
    historical_impact: float  # What actually happened to the market
    regime_at_time: MarketRegime


class HybridSimilarityEngine:
    """Multi-dimensional similarity scoring engine.

    Combines semantic embedding distance with structured metadata
    overlap to find historically similar events.
    """

    def __init__(self, weights: SimilarityWeights | None = None) -> None:
        """Initialize with optional custom weights."""
        self.weights = weights or SimilarityWeights()

    def compute_similarity(
        self,
        query: EventOntologySchema,
        candidate: EventOntologySchema,
        semantic_score: float,
        query_regime: MarketRegime,
        candidate_regime: MarketRegime,
        query_volatility: float = 0.0,
        candidate_volatility: float = 0.0,
        query_exposure: float | None = None,
        candidate_exposure: float | None = None,
        query_structure: list[str] | None = None,
        candidate_structure: list[str] | None = None,
    ) -> SimilarityBreakdown:
        """Compute the full hybrid similarity between two events.

        Args:
            query: The current event we're analyzing.
            candidate: A historical event to compare against.
            semantic_score: Pre-computed cosine similarity from Qdrant (0-1).
            query_regime: Current market regime.
            candidate_regime: Regime when the historical event occurred.
            query_volatility: Current annualized volatility.
            candidate_volatility: Volatility when the historical event occurred.
        """
        sector = self._jaccard(query.affected_sectors, candidate.affected_sectors)
        geo = self._jaccard(query.affected_countries, candidate.affected_countries)
        regime = self._regime_similarity(query_regime, candidate_regime)
        vol = self._volatility_similarity(query_volatility, candidate_volatility)
        severity = self._numeric_proximity(query.severity_score, candidate.severity_score)
        magnitude = self._numeric_proximity(
            query.estimated_disruption_magnitude, candidate.estimated_disruption_magnitude
        )
        duration = self._numeric_proximity(
            float(query.estimated_duration_days) if query.estimated_duration_days is not None else None,
            float(candidate.estimated_duration_days) if candidate.estimated_duration_days is not None else None,
        )
        exposure = self._numeric_proximity(query_exposure, candidate_exposure)
        structural = self._jaccard(query_structure or [], candidate_structure or [])

        overall = (
            self.weights.semantic * semantic_score
            + self.weights.sector * sector
            + self.weights.geographic * geo
            + self.weights.regime * regime
            + self.weights.volatility * vol
            + self.weights.severity_similarity * severity
            + self.weights.magnitude_similarity * magnitude
            + self.weights.duration_similarity * duration
            + self.weights.exposure_similarity * exposure
            + self.weights.structural_similarity * structural
        )

        return SimilarityBreakdown(
            overall_score=round(overall, 4),
            semantic_score=round(semantic_score, 4),
            sector_score=round(sector, 4),
            geographic_score=round(geo, 4),
            regime_score=round(regime, 4),
            volatility_score=round(vol, 4),
            severity_score=round(severity, 4),
            magnitude_score=round(magnitude, 4),
            duration_score=round(duration, 4),
            exposure_score=round(exposure, 4),
            structural_score=round(structural, 4),
            weights=self.weights,
        )

    @staticmethod
    def _jaccard(set_a: list[str], set_b: list[str]) -> float:
        """Compute Jaccard similarity between two lists of strings."""
        a = set(s.lower() for s in set_a)
        b = set(s.lower() for s in set_b)

        if not a and not b:
            return 1.0  # Both empty = same scope
        if not a or not b:
            return 0.0

        intersection = len(a & b)
        union = len(a | b)
        return intersection / union

    @staticmethod
    def _regime_similarity(regime_a: MarketRegime, regime_b: MarketRegime) -> float:
        """Score regime similarity (exact match = 1.0, partial = 0.5, different = 0.0)."""
        if regime_a == regime_b:
            return 1.0

        # Partial matches (both bull or both bear)
        bull_regimes = {MarketRegime.BULL_LOW_VOL, MarketRegime.BULL_HIGH_VOL}
        bear_regimes = {MarketRegime.BEAR_LOW_VOL, MarketRegime.BEAR_HIGH_VOL, MarketRegime.CRISIS}

        if (regime_a in bull_regimes and regime_b in bull_regimes):
            return 0.7
        if (regime_a in bear_regimes and regime_b in bear_regimes):
            return 0.7

        return 0.0

    @staticmethod
    def _volatility_similarity(vol_a: float, vol_b: float) -> float:
        """Score volatility similarity using exponential decay of difference."""
        if vol_a == 0 and vol_b == 0:
            return 1.0

        diff = abs(vol_a - vol_b)
        # Exponential decay: diff of 0 → 1.0, diff of 0.5 → ~0.07
        import math
        return math.exp(-5 * diff)

    @staticmethod
    def _numeric_proximity(value_a: float | None, value_b: float | None) -> float:
        """Score comparable numeric magnitudes without treating missing values as equal."""
        if value_a is None and value_b is None:
            return 0.5
        if value_a is None or value_b is None:
            return 0.25
        scale = max(abs(value_a), abs(value_b), 0.01)
        return max(0.0, 1.0 - abs(value_a - value_b) / scale)

    def rank_candidates(
        self,
        query: EventOntologySchema,
        candidates: list[tuple[EventOntologySchema, float, MarketRegime, float]],
        query_regime: MarketRegime,
        query_volatility: float,
        top_k: int = 10,
    ) -> list[tuple[EventOntologySchema, SimilarityBreakdown]]:
        """Rank candidate events by hybrid similarity score.

        Args:
            query: Current event.
            candidates: List of (event, semantic_score, regime, volatility) tuples.
            query_regime: Current market regime.
            query_volatility: Current annualized volatility.
            top_k: Number of top results to return.

        Returns:
            Sorted list of (event, breakdown) tuples, highest similarity first.
        """
        scored = []
        for event, sem_score, cand_regime, cand_vol in candidates:
            breakdown = self.compute_similarity(
                query=query,
                candidate=event,
                semantic_score=sem_score,
                query_regime=query_regime,
                candidate_regime=cand_regime,
                query_volatility=query_volatility,
                candidate_volatility=cand_vol,
            )
            scored.append((event, breakdown))

        # Sort by overall score descending
        scored.sort(key=lambda x: x[1].overall_score, reverse=True)
        return scored[:top_k]
