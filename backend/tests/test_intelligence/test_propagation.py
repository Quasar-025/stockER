from datetime import datetime, timedelta, timezone

from app.graph.historical_observations import CausalRelationshipObservation
from app.graph.queries import InMemoryCausalGraph
from app.graph.schema import (
    CHANNEL_FOR_RELATIONSHIP,
    CausalEdge,
    EstimationMetadata,
    EstimationMethod,
    RelationshipType,
    VerificationStatus,
)
from app.intelligence.effect_decomposition import ReliabilityCalibrator, ReliabilityValidationRecord
from app.intelligence.ontology import EventCategory, EventOntologySchema
from app.intelligence.propagation import PropagationEngine
from app.intelligence.regime import MarketRegime


def _edge(relationship: RelationshipType) -> CausalEdge:
    now = datetime.now(timezone.utc) - timedelta(days=1)
    return CausalEdge(
        source_entity="TSM", target_entity="NVDA", relationship_type=relationship,
        channel_type=CHANNEL_FOR_RELATIONSHIP[relationship], strength=0.8, dependency_exposure=0.7,
        substitutability=0.5, historical_coefficient=0.5, historical_observation_count=6,
        estimation_metadata=EstimationMetadata(sample_count=6, estimation_method=EstimationMethod.OLS_REGRESSION, is_prior=False),
        typical_time_lag_days=3, relationship_created_at=now, relationship_verified_at=now,
        source_date=now, temporal_approximation=False, confidence=0.8, evidence_count=1,
        evidence_sources=["controlled test fixture"], verification_status=VerificationStatus.VERIFIED,
    )


def _event() -> EventOntologySchema:
    now = datetime.now(timezone.utc)
    return EventOntologySchema(
        title="TSMC disruption", description="capacity disruption", source_url="https://example.test/event",
        published_at=now, event_date=now, category=EventCategory.SUPPLY_CHAIN_DISRUPTION,
        severity_score=0.8, estimated_disruption_magnitude=0.5, estimated_duration_days=7,
        affected_tickers=["TSM"], affected_sectors=["Semiconductors"], affected_countries=["Taiwan"],
    )


def _observations() -> list[CausalRelationshipObservation]:
    now = datetime.now(timezone.utc)
    return [
        CausalRelationshipObservation(
            event_id=f"event-{index}", event_date=now - timedelta(days=200 + index), available_at=now - timedelta(days=100),
            source_entity="TSM", target_entity="NVDA", event_magnitude=0.5, event_duration_days=7,
            market_regime=MarketRegime.BEAR_HIGH_VOL, source_return=-0.01 * (index + 1),
            target_return=-0.005 * (index + 1), market_return=-0.001, sector_excess_return=-0.001,
            evidence_reference="controlled test fixture",
        ) for index in range(6)
    ]


def test_propagation_uses_observed_direction_not_supply_label() -> None:
    calibration = [ReliabilityValidationRecord(feature_score=0.7, outcome_was_correct=True) for _ in range(12)]
    engine = PropagationEngine(
        InMemoryCausalGraph([_edge(RelationshipType.SUPPLIES)]), _observations(),
        reliability_calibrator=ReliabilityCalibrator(calibration),
    )
    result = engine.forecast(_event(), MarketRegime.BEAR_HIGH_VOL)
    nvda = next(impact for impact in result.primary_impacts if impact.ticker == "NVDA" and impact.time_horizon_days == 3)

    assert nvda.direction_probability > 0.5
    assert nvda.model_confidence != nvda.direction_probability
    assert nvda.effect_decomposition.direct_event_effect.sample_count == 6
    assert nvda.effect_decomposition.market_effect.channel_name == "market"


def test_competition_is_potential_channel_not_guaranteed_benefit() -> None:
    engine = PropagationEngine(InMemoryCausalGraph([_edge(RelationshipType.COMPETES_WITH)]), _observations())
    result = engine.forecast(_event(), MarketRegime.BEAR_HIGH_VOL)

    assert result.potential_beneficiaries
    assert result.potential_beneficiaries[0].direction == "UNCERTAIN"
