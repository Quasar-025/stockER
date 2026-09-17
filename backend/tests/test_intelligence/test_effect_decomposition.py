from app.intelligence.effect_decomposition import (
    EffectChannel,
    EffectDecomposition,
    ReliabilityCalibrator,
    ReliabilityInputs,
    ReliabilityValidationRecord,
)


def _channel(name: str, effect: float = 0.0) -> EffectChannel:
    return EffectChannel(
        channel_name=name, estimated_effect=effect, probability=0.5, confidence=0.4,
        sample_count=6, estimation_method="historical_regression", evidence_summary="test",
    )


def test_effect_decomposition_has_all_channels() -> None:
    decomposition = EffectDecomposition.combine(
        direct_event_effect=_channel("direct", -0.01), sector_effect=_channel("sector", -0.002),
        market_effect=_channel("market", 0.001), competitive_substitution_effect=_channel("competition", 0.003),
        residual_effect=_channel("residual", 0.0), net_direction_probability=0.7, model_confidence=0.5,
    )

    assert decomposition.net_expected_return == -0.008
    assert decomposition.competitive_substitution_effect.channel_name == "competition"


def test_confidence_is_calibrated_not_a_naive_product() -> None:
    inputs = ReliabilityInputs(
        sample_count=20, consistency=0.8, similarity_quality=0.7, data_quality=0.9,
        edge_confidence=0.8, model_uncertainty=0.2,
    )
    records = [ReliabilityValidationRecord(feature_score=0.7, outcome_was_correct=True) for _ in range(8)]
    records.extend(ReliabilityValidationRecord(feature_score=0.7, outcome_was_correct=False) for _ in range(4))
    result = ReliabilityCalibrator(records).estimate(inputs)

    assert result.is_calibrated is True
    assert result.value != 20 * 0.8 * 0.7 * 0.9 * 0.8 * 0.8
