"""Controlled end-to-end MDC test; fixtures are not claimed as empirical data."""

from datetime import datetime, timedelta, timezone

from app.graph.historical_observations import CausalRelationshipObservation
from app.graph.queries import InMemoryCausalGraph
from app.graph.schema import CHANNEL_FOR_RELATIONSHIP, CausalEdge, EstimationMetadata, EstimationMethod, RelationshipType, VerificationStatus
from app.intelligence.effect_decomposition import ReliabilityCalibrator, ReliabilityValidationRecord
from app.intelligence.ontology import EventCategory, EventOntologySchema
from app.intelligence.propagation import PropagationEngine
from app.intelligence.regime import MarketRegime


def test_tsmc_disruption_mdc_end_to_end() -> None:
    now = datetime.now(timezone.utc)
    def edge(source: str, target: str, relation: RelationshipType, lag: int) -> CausalEdge:
        return CausalEdge(source_entity=source,target_entity=target,relationship_type=relation,channel_type=CHANNEL_FOR_RELATIONSHIP[relation],strength=.8,dependency_exposure=.7,substitutability=.5,historical_coefficient=.5,historical_observation_count=6,estimation_metadata=EstimationMetadata(sample_count=6,estimation_method=EstimationMethod.OLS_REGRESSION,is_prior=False),typical_time_lag_days=lag,relationship_created_at=now-timedelta(days=1),relationship_verified_at=now-timedelta(days=1),source_date=now-timedelta(days=1),temporal_approximation=False,confidence=.8,evidence_count=1,evidence_sources=["controlled fixture"],verification_status=VerificationStatus.VERIFIED)
    observations = [CausalRelationshipObservation(event_id=str(i),event_date=now-timedelta(days=100+i),available_at=now-timedelta(days=10),source_entity="TSM",target_entity="NVDA",event_magnitude=.4,event_duration_days=7,market_regime=MarketRegime.BEAR_HIGH_VOL,source_return=-.01*(i+1),target_return=-.005*(i+1),market_return=-.001,sector_excess_return=-.001,evidence_reference="controlled fixture") for i in range(6)]
    event = EventOntologySchema(title="TSMC disruption",description="test",source_url="https://example.test/tsmc",published_at=now,event_date=now,category=EventCategory.SUPPLY_CHAIN_DISRUPTION,severity_score=.8,estimated_disruption_magnitude=.4,estimated_duration_days=7,affected_tickers=["TSM"])
    calibration = ReliabilityCalibrator([ReliabilityValidationRecord(.7, True) for _ in range(12)])
    forecast = PropagationEngine(InMemoryCausalGraph([edge("TSM","NVDA",RelationshipType.SUPPLIES,3),edge("NVDA","MSFT",RelationshipType.SUPPLIES,3),edge("MSFT","ORCL",RelationshipType.COMPETES_WITH,3)]),observations,reliability_calibrator=calibration).forecast(event,MarketRegime.BEAR_HIGH_VOL,max_depth=4)
    nvda = next(item for item in forecast.primary_impacts if item.ticker == "NVDA" and item.time_horizon_days == 3)
    assert nvda.direction_probability != nvda.model_confidence
    assert nvda.effect_decomposition.direct_event_effect.sample_count == 6
    assert nvda.causal_paths[0].evidence_sources
    assert forecast.secondary_impacts and forecast.potential_beneficiaries
    assert all(item.historical_support.sample_count >= 0 for item in forecast.primary_impacts)
    assert all("CORRELATED_WITH" not in path.relationship_types for item in forecast.primary_impacts for path in item.causal_paths)
