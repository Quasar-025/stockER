from datetime import datetime, timezone

from app.intelligence.ontology import EventCategory, EventOntologySchema
from app.intelligence.regime import MarketRegime
from app.intelligence.similarity import HybridSimilarityEngine


def _event(magnitude: float, duration: int) -> EventOntologySchema:
    return EventOntologySchema(
        title="Semiconductor disruption", description="test", source_url=f"https://example.test/{magnitude}",
        published_at=datetime.now(timezone.utc), category=EventCategory.SUPPLY_CHAIN_DISRUPTION,
        severity_score=0.8, estimated_disruption_magnitude=magnitude, estimated_duration_days=duration,
        affected_sectors=["Semiconductors"], affected_countries=["Taiwan"],
    )


def test_similarity_conditions_on_magnitude_and_duration() -> None:
    engine = HybridSimilarityEngine()
    query = _event(0.30, 30)
    comparable = engine.compute_similarity(query, _event(0.28, 28), 0.8, MarketRegime.BEAR_HIGH_VOL, MarketRegime.BEAR_HIGH_VOL)
    small_short = engine.compute_similarity(query, _event(0.02, 2), 0.8, MarketRegime.BEAR_HIGH_VOL, MarketRegime.BEAR_HIGH_VOL)

    assert comparable.magnitude_score > small_short.magnitude_score
    assert comparable.duration_score > small_short.duration_score
    assert comparable.overall_score > small_short.overall_score
