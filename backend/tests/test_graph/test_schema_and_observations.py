from datetime import UTC, datetime, timedelta

from app.graph.historical_observations import (
    CausalRelationshipObservation,
    HistoricalEdgeCalibrator,
)
from app.graph.queries import InMemoryCausalGraph, filter_edges_point_in_time
from app.graph.schema import ChannelType, RelationshipType
from app.graph.seed import semiconductor_seed_edges
from app.intelligence.regime import MarketRegime


def test_edges_have_confidence_evidence_and_temporal_metadata() -> None:
    edge = semiconductor_seed_edges()[0]

    assert edge.confidence > 0
    assert edge.evidence_sources
    assert edge.relationship_created_at is not None
    assert edge.estimation_metadata.is_prior is True
    assert edge.historical_coefficient is None


def test_correlated_edges_are_contextual_not_causal() -> None:
    graph = InMemoryCausalGraph(semiconductor_seed_edges())
    correlated = [edge for edge in graph.edges if edge.relationship_type == RelationshipType.CORRELATED_WITH][0]

    assert correlated.channel_type == ChannelType.COMMON_FACTOR
    assert correlated.participates_in_causal_propagation is False
    assert all(path[-1].relationship_type != RelationshipType.CORRELATED_WITH for path, _ in graph.traverse(["TSM"], max_depth=3, allow_temporal_approximation=True))


def test_point_in_time_excludes_temporal_approximations_by_default() -> None:
    edge = semiconductor_seed_edges()[0]
    as_of = edge.relationship_created_at + timedelta(days=1)

    assert filter_edges_point_in_time([edge], as_of) == []
    assert filter_edges_point_in_time([edge], as_of, allow_temporal_approximation=True) == [edge]


def test_coefficient_is_learned_only_from_sufficient_observations() -> None:
    now = datetime.now(UTC)
    observations = [
        CausalRelationshipObservation(
            event_id=str(index), event_date=now - timedelta(days=100 - index), available_at=now - timedelta(days=50),
            source_entity="TSM", target_entity="NVDA", event_magnitude=0.5, event_duration_days=7,
            market_regime=MarketRegime.BEAR_HIGH_VOL, source_return=-0.01 * (index + 1),
            target_return=-0.004 * (index + 1), market_return=-0.001, sector_excess_return=-0.001,
            evidence_reference="controlled test fixture",
        ) for index in range(6)
    ]
    calibration = HistoricalEdgeCalibrator().estimate(
        observations, source_entity="TSM", target_entity="NVDA", event_magnitude=0.5,
        event_duration_days=7, market_regime=MarketRegime.BEAR_HIGH_VOL, as_of=now,
    )

    assert calibration.coefficient is not None
    assert calibration.metadata.is_prior is False
    assert calibration.metadata.sample_count == 6


def test_no_deterministic_direction_from_relationship_type() -> None:
    with open("app/graph/schema.py", encoding="utf-8") as source_file:
        source = source_file.read()
    mapping = source.split("CHANNEL_FOR_RELATIONSHIP", 1)[1].split("class EstimationMetadata", 1)[0]
    assert "BEARISH" not in mapping
    assert "BULLISH" not in mapping
