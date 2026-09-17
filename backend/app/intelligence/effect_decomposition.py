"""Inspectable channel-level effect attribution and reliability calibration."""

from dataclasses import dataclass
from math import log1p
from typing import Iterable

from pydantic import BaseModel, Field


class EffectChannel(BaseModel):
    """One separately estimated contribution to an entity return."""

    channel_name: str
    estimated_effect: float
    probability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    sample_count: int = Field(ge=0)
    estimation_method: str
    evidence_summary: str
    is_prior: bool = False


class EffectDecomposition(BaseModel):
    """Return attribution with causal and common-factor channels kept apart."""

    direct_event_effect: EffectChannel
    sector_effect: EffectChannel
    market_effect: EffectChannel
    competitive_substitution_effect: EffectChannel
    residual_effect: EffectChannel
    net_expected_return: float
    net_direction_probability: float = Field(ge=0.0, le=1.0)
    model_confidence: float = Field(ge=0.0, le=1.0)

    @classmethod
    def combine(
        cls,
        *,
        direct_event_effect: EffectChannel,
        sector_effect: EffectChannel,
        market_effect: EffectChannel,
        competitive_substitution_effect: EffectChannel,
        residual_effect: EffectChannel,
        net_direction_probability: float,
        model_confidence: float,
    ) -> "EffectDecomposition":
        channels = (
            direct_event_effect, sector_effect, market_effect,
            competitive_substitution_effect, residual_effect,
        )
        return cls(
            direct_event_effect=direct_event_effect, sector_effect=sector_effect,
            market_effect=market_effect, competitive_substitution_effect=competitive_substitution_effect,
            residual_effect=residual_effect,
            net_expected_return=sum(channel.estimated_effect for channel in channels),
            net_direction_probability=net_direction_probability, model_confidence=model_confidence,
        )


@dataclass(frozen=True)
class ReliabilityInputs:
    """Measured reliability drivers; these never encode outcome direction."""

    sample_count: int
    consistency: float
    similarity_quality: float
    data_quality: float
    edge_confidence: float
    model_uncertainty: float

    def feature_score(self) -> float:
        """A bounded additive score, intentionally not a product of scores."""

        sample_score = min(log1p(max(self.sample_count, 0)) / log1p(30), 1.0)
        values = (self.consistency, self.similarity_quality, self.data_quality, self.edge_confidence)
        if any(not 0.0 <= value <= 1.0 for value in values) or not 0.0 <= self.model_uncertainty <= 1.0:
            raise ValueError("Reliability inputs must be bounded in [0, 1]")
        # Coefficients are interpretable feature weights, not probabilistic
        # transmission constants.  Held-out outcome data calibrates this score.
        return max(
            0.0,
            min(
                1.0,
                0.28 * sample_score
                + 0.22 * self.consistency
                + 0.18 * self.similarity_quality
                + 0.12 * self.data_quality
                + 0.12 * self.edge_confidence
                + 0.08 * (1.0 - self.model_uncertainty),
            ),
        )


@dataclass(frozen=True)
class ReliabilityValidationRecord:
    feature_score: float
    outcome_was_correct: bool


@dataclass(frozen=True)
class ReliabilityEstimate:
    value: float
    is_calibrated: bool
    calibration_sample_count: int
    reason: str


class ReliabilityCalibrator:
    """Calibrate forecast reliability against held-out directional outcomes.

    With adequate validation observations, bin-level empirical correctness with
    Beta(1,1) smoothing maps feature quality to reliability.  Without it the
    result is a deliberately low *uncalibrated* confidence proxy and should be
    flagged instead of presented as broadly reliable.
    """

    def __init__(self, records: Iterable[ReliabilityValidationRecord] = (), min_calibration_samples: int = 10) -> None:
        self.records = tuple(records)
        self.min_calibration_samples = min_calibration_samples

    def estimate(self, inputs: ReliabilityInputs) -> ReliabilityEstimate:
        score = inputs.feature_score()
        if len(self.records) < self.min_calibration_samples:
            return ReliabilityEstimate(
                value=round(min(0.25, 0.05 + 0.25 * score), 4), is_calibrated=False,
                calibration_sample_count=len(self.records),
                reason="Insufficient held-out outcomes to calibrate reliability.",
            )
        lower, upper = self._bin(score)
        matching = [record for record in self.records if lower <= record.feature_score < upper]
        if len(matching) < 3:
            matching = list(self.records)
        successes = sum(record.outcome_was_correct for record in matching)
        # Beta(1,1) smoothed empirical accuracy avoids certainty from a tiny bin.
        calibrated = (successes + 1) / (len(matching) + 2)
        return ReliabilityEstimate(
            value=round(calibrated, 4), is_calibrated=True,
            calibration_sample_count=len(self.records), reason="Held-out outcome calibration.",
        )

    @staticmethod
    def _bin(score: float) -> tuple[float, float]:
        start = min(0.8, int(score * 5) / 5)
        return start, start + 0.2 + 1e-12
