"""Market Impact Engine — regime-aware forecasting.

Takes the output of the similarity engine (similar historical events)
and produces a Forecast object by statistically aggregating the
historical outcomes, weighted by similarity and regime match.

No LLM here — pure statistical aggregation.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.intelligence.distribution import EmpiricalImpactDistribution
from app.intelligence.effect_decomposition import ReliabilityCalibrator, ReliabilityInputs
from app.intelligence.ontology import EventOntologySchema
from app.intelligence.regime import MarketRegime
from app.intelligence.similarity import SimilarityBreakdown

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """Output of the Market Impact Engine."""

    event_id: uuid.UUID
    ticker: str
    predicted_impact: float  # e.g., -0.05 for -5%
    confidence_score: float  # 0-1
    time_horizon_days: int
    market_regime: MarketRegime
    similar_events: list[dict]  # List of similar event summaries
    causal_chain: list[str]  # Causal propagation path
    created_at: datetime
    # V2 fields remain distinct: likelihood is not reliability.
    direction_probability: float = 0.0
    model_confidence: float = 0.0
    confidence_is_calibrated: bool = False
    sample_count: int = 0
    return_p25: float = 0.0
    return_p50: float = 0.0
    return_p75: float = 0.0
    insufficient_historical_evidence: bool = True
    company_name: str | None = None


class MarketImpactEngine:
    """Produces forecasts from similarity engine output.

    Uses weighted average of historical outcomes, discounted by
    similarity score, to produce an expected market impact.
    """

    def __init__(
        self,
        min_confidence: float = 0.3,
        default_horizon_days: int = 30,
        reliability_calibrator: ReliabilityCalibrator | None = None,
    ) -> None:
        """Initialize with minimum confidence threshold."""
        self.min_confidence = min_confidence
        self.default_horizon_days = default_horizon_days
        self.reliability_calibrator = reliability_calibrator or ReliabilityCalibrator()

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
                created_at=datetime.now(UTC),
                direction_probability=0.0,
                model_confidence=0.0,
                confidence_is_calibrated=False,
                sample_count=0,
                insufficient_historical_evidence=True,
            )

        # Weighted average of historical impacts
        total_weight = 0.0
        weighted_impact = 0.0
        event_summaries = []

        for hist_event, breakdown, hist_impact in similar_events:
            weight = breakdown.overall_score
            weighted_impact += weight * hist_impact
            total_weight += weight

            event_summaries.append(
                {
                    "title": hist_event.title,
                    "category": hist_event.category.value,
                    "similarity_score": breakdown.overall_score,
                    "historical_impact": hist_impact,
                    "regime_at_time": breakdown.regime_score,
                }
            )

        # Compute prediction
        predicted_impact = weighted_impact / total_weight if total_weight > 0 else 0.0

        # Similarity and count provide inputs to a reliability calibration, not
        # a multiplication that can be misrepresented as a probability.
        avg_similarity = total_weight / len(similar_events) if similar_events else 0
        impact_distribution = EmpiricalImpactDistribution.from_returns(
            [impact for _, _, impact in similar_events]
        )
        uncertainty = min(1.0, (impact_distribution.standard_error or 0.05) / 0.05)
        reliability = self.reliability_calibrator.estimate(
            ReliabilityInputs(
                sample_count=len(similar_events),
                consistency=impact_distribution.historical_consistency,
                similarity_quality=avg_similarity,
                data_quality=1.0,
                edge_confidence=1.0,
                model_uncertainty=uncertainty,
            )
        )
        direction_probability = max(
            impact_distribution.probability_negative,
            impact_distribution.probability_positive,
            impact_distribution.probability_neutral,
        )
        confidence = reliability.value

        return ForecastResult(
            event_id=uuid.uuid4(),
            ticker=ticker,
            predicted_impact=round(predicted_impact, 4),
            confidence_score=round(min(confidence, 1.0), 4),
            time_horizon_days=self.default_horizon_days,
            market_regime=current_regime,
            similar_events=event_summaries,
            causal_chain=causal_chain or [],
            created_at=datetime.now(UTC),
            direction_probability=round(direction_probability, 4),
            model_confidence=round(confidence, 4),
            confidence_is_calibrated=reliability.is_calibrated,
            sample_count=len(similar_events),
            return_p25=impact_distribution.quantiles.p25,
            return_p50=impact_distribution.quantiles.p50,
            return_p75=impact_distribution.quantiles.p75,
            insufficient_historical_evidence=(
                len(similar_events) <= 5
                or not reliability.is_calibrated
                or confidence < self.min_confidence
            ),
        )

    def compute_probabilistic_forecast(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Delegate multi-entity causal forecasting to ``PropagationEngine``.

        The explicit engine parameter avoids creating graph/database clients
        behind the caller's back and preserves this legacy API for existing
        single-ticker workflows.
        """

        propagation_engine = kwargs.pop("propagation_engine")
        return propagation_engine.forecast(*args, **kwargs)
