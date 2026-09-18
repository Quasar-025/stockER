from datetime import datetime, timezone

from app.graph.queries import InMemoryCausalGraph
from app.intelligence.ontology import EventCategory, EventOntologySchema
from app.intelligence.propagation import PropagationEngine
from app.intelligence.regime import MarketRegime


def test_probability_and_confidence_are_separate_in_public_schema() -> None:
    now = datetime.now(timezone.utc)
    event = EventOntologySchema(
        title="Evidence-poor event", description="test", source_url="https://example.test/no-history",
        published_at=now, category=EventCategory.SUPPLY_CHAIN_DISRUPTION, severity_score=0.8,
        estimated_disruption_magnitude=0.7, estimated_duration_days=14, affected_tickers=["TSM"],
    )
    forecast = PropagationEngine(InMemoryCausalGraph([])).forecast(event, MarketRegime.BEAR_HIGH_VOL)
    impact = forecast.primary_impacts[0]

    assert impact.direction_probability == 0.5
    assert impact.model_confidence < impact.direction_probability
    assert impact.insufficient_historical_evidence is True
    assert impact.effect_decomposition is not None
