"""Market Impact Engine — regime-aware forecasting.

Takes the output of the similarity engine (similar historical events)
and produces a Forecast object by statistically aggregating the
historical outcomes, weighted by similarity and regime match.

No LLM here — pure statistical aggregation.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.intelligence.ontology import EventOntologySchema
from app.intelligence.similarity import SimilarityBreakdown
from app.intelligence.regime import MarketRegime

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """Output of the Market Impact Engine."""

    event_id: uuid.UUID
    ticker: str
    predicted_impact: float      # e.g., -0.05 for -5%
    confidence_score: float      # 0-1
    time_horizon_days: int
    market_regime: MarketRegime
    similar_events: list[dict]   # List of similar event summaries
    causal_chain: list[str]      # Causal propagation path
    created_at: datetime


class MarketImpactEngine:
    """Produces forecasts from similarity engine output.

    Uses weighted average of historical outcomes, discounted by
    similarity score, to produce an expected market impact.
    """

    def __init__(self, min_confidence: float = 0.3, default_horizon_days: int = 30) -> None:
        """Initialize with minimum confidence threshold."""
        self.min_confidence = min_confidence
        self.default_horizon_days = default_horizon_days

    def compute_forecast(
        self,
        event: EventOntologySchema,
        ticker: str,
        similar_events: list[tuple[EventOntologySchema, SimilarityBreakdown, float]],
        current_regime: MarketRegime,
        causal_chain: list[str] | None = None,
    ) -> ForecastResult:
        """Compute a market impact forecast.

        Args:
            event: The current event being analyzed.
            ticker: The stock ticker to forecast impact for.
            similar_events: List of (event, similarity_breakdown, historical_impact) tuples.
            current_regime: Current market regime.
            causal_chain: Optional causal propagation path from Neo4j.

        Returns:
            ForecastResult with predicted impact and confidence.
        """
        if not similar_events:
            return ForecastResult(
                event_id=uuid.uuid4(),
                ticker=ticker,
                predicted_impact=0.0,
                confidence_score=0.0,
                time_horizon_days=self.default_horizon_days,
                market_regime=current_regime,
                similar_events=[],
                causal_chain=causal_chain or [],
                created_at=datetime.now(timezone.utc),
            )

        # Weighted average of historical impacts
        total_weight = 0.0
        weighted_impact = 0.0
        event_summaries = []

        for hist_event, breakdown, hist_impact in similar_events:
            weight = breakdown.overall_score
            weighted_impact += weight * hist_impact
            total_weight += weight

            event_summaries.append({
                "title": hist_event.title,
                "category": hist_event.category.value,
                "similarity_score": breakdown.overall_score,
                "historical_impact": hist_impact,
                "regime_at_time": breakdown.regime_score,
            })

        # Compute prediction
        if total_weight > 0:
            predicted_impact = weighted_impact / total_weight
        else:
            predicted_impact = 0.0

        # Confidence = average similarity * coverage factor
        avg_similarity = total_weight / len(similar_events) if similar_events else 0
        coverage = min(len(similar_events) / 5, 1.0)  # More events = higher confidence
        confidence = avg_similarity * coverage

        return ForecastResult(
            event_id=uuid.uuid4(),
            ticker=ticker,
            predicted_impact=round(predicted_impact, 4),
            confidence_score=round(min(confidence, 1.0), 4),
            time_horizon_days=self.default_horizon_days,
            market_regime=current_regime,
            similar_events=event_summaries,
            causal_chain=causal_chain or [],
            created_at=datetime.now(timezone.utc),
        )
