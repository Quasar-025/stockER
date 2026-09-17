from app.intelligence.distribution import EmpiricalImpactDistribution


def test_quantiles_are_explicitly_summaries_not_a_parametric_distribution() -> None:
    summary = EmpiricalImpactDistribution.from_returns([-0.03, -0.01, 0.02, 0.04])

    assert summary.quantiles.p25 < summary.quantiles.p75
    assert summary.sample_count == 4
    assert summary.probability_negative == 0.5
    assert summary.probability_positive == 0.5


def test_empty_history_returns_direction_neutral_prior() -> None:
    summary = EmpiricalImpactDistribution.from_returns([])

    assert summary.is_prior is True
    assert summary.sample_count == 0
    assert summary.quantiles.p50 == 0.0
