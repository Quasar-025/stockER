from app.data.landmarks import load_landmark_manifest
from app.models.historical import CanonicalEvent, HistoricalEventOutcome


def test_landmark_manifest_does_not_masquerade_as_empirical_outcomes() -> None:
    records = load_landmark_manifest()

    assert 50 <= len(records) <= 100
    assert all(record["bootstrap_status"] == "outcomes_uncollected" for record in records)
    assert all(record["outcomes"] is None for record in records)


def test_historical_models_expose_point_in_time_and_seed_status() -> None:
    assert "available_at" in HistoricalEventOutcome.__table__.c
    assert "is_seeded_demo" in HistoricalEventOutcome.__table__.c
    assert "estimated_disruption_magnitude" in CanonicalEvent.__table__.c
