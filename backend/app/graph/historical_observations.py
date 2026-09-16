"""Observed edge activations and conservative coefficient estimation."""

from dataclasses import dataclass
from datetime import datetime
from math import sqrt

from pydantic import BaseModel, Field

from app.graph.schema import EstimationMetadata, EstimationMethod
from app.intelligence.regime import MarketRegime


class CausalRelationshipObservation(BaseModel):
    """One actual historical activation of a potential graph channel.

    ``target_residual_return`` removes observed market and sector excess terms
    before estimating an edge-specific effect.  Demo/fixture observations are
    ignored unless a caller deliberately opts in for a test-only scenario.
    """

    event_id: str
    event_date: datetime
    available_at: datetime
    source_entity: str
    target_entity: str
    event_magnitude: float | None = Field(default=None, ge=0.0, le=1.0)
    event_duration_days: int | None = Field(default=None, ge=0)
    market_regime: MarketRegime | None = None
    source_return: float
    target_return: float
    market_return: float = 0.0
    sector_excess_return: float = 0.0
    data_quality: float = Field(default=1.0, ge=0.0, le=1.0)
    is_seeded_demo: bool = False
    evidence_reference: str | None = None

    @property
    def target_residual_return(self) -> float:
        return self.target_return - self.market_return - self.sector_excess_return


@dataclass(frozen=True)
class WeightedObservation:
    observation: CausalRelationshipObservation
    similarity_weight: float


@dataclass(frozen=True)
class EdgeCalibration:
    """Result of data estimation or a documented direction-neutral prior."""

    coefficient: float | None
    transmission_probability: float
    metadata: EstimationMetadata
    comparable_observations: tuple[WeightedObservation, ...]
    residual_returns: tuple[float, ...]
    is_insufficient_evidence: bool


class HistoricalEdgeCalibrator:
    """Estimate edge response from available, comparable observations.

    A six-observation threshold is deliberately conservative for this MVP.
    Under it, no directional coefficient is fabricated: only a broad,
    direction-neutral channel activation prior is returned.
    """

    def __init__(self, min_observations: int = 6) -> None:
        self.min_observations = min_observations

    def comparable(
        self,
        observations: list[CausalRelationshipObservation],
        *,
        source_entity: str,
        target_entity: str,
        event_magnitude: float | None,
        event_duration_days: int | None,
        market_regime: MarketRegime | None,
        as_of: datetime | None = None,
        include_seeded_demo: bool = False,
    ) -> list[WeightedObservation]:
        """Retrieve observations with magnitude, duration, regime and PIT filters."""

        candidates: list[WeightedObservation] = []
        for observation in observations:
            if observation.source_entity != source_entity or observation.target_entity != target_entity:
                continue
            if as_of is not None and observation.available_at > as_of:
                continue
            if observation.is_seeded_demo and not include_seeded_demo:
                continue
            magnitude_score = self._proximity(event_magnitude, observation.event_magnitude)
            duration_score = self._proximity(
                float(event_duration_days) if event_duration_days is not None else None,
                float(observation.event_duration_days) if observation.event_duration_days is not None else None,
            )
            regime_score = 1.0 if market_regime is None or observation.market_regime == market_regime else 0.35
            # This is a similarity weighting for estimation, not confidence.
            similarity = (magnitude_score + duration_score + regime_score) / 3.0
            candidates.append(WeightedObservation(observation=observation, similarity_weight=similarity))
        return candidates

    def estimate(
        self,
        observations: list[CausalRelationshipObservation],
        **conditions: object,
    ) -> EdgeCalibration:
        """Estimate weighted OLS coefficient, or return an explicit prior."""

        comparable = self.comparable(observations, **conditions)  # type: ignore[arg-type]
        usable = [entry for entry in comparable if entry.similarity_weight >= 0.25]
        residuals = tuple(entry.observation.target_residual_return for entry in usable)
        if len(usable) < self.min_observations:
            return EdgeCalibration(
                coefficient=None,
                transmission_probability=0.5,
                metadata=EstimationMetadata(
                    sample_count=len(usable),
                    estimation_method=EstimationMethod.INSUFFICIENT_DATA,
                    estimation_window=None,
                    standard_error=None,
                    is_prior=True,
                ),
                comparable_observations=tuple(usable),
                residual_returns=residuals,
                is_insufficient_evidence=True,
            )

        weights = [entry.similarity_weight * entry.observation.data_quality for entry in usable]
        x_values = [entry.observation.source_return for entry in usable]
        y_values = list(residuals)
        weight_sum = sum(weights)
        x_mean = sum(weight * value for weight, value in zip(weights, x_values)) / weight_sum
        y_mean = sum(weight * value for weight, value in zip(weights, y_values)) / weight_sum
        denominator = sum(weight * (value - x_mean) ** 2 for weight, value in zip(weights, x_values))
        if denominator <= 1e-12:
            return EdgeCalibration(
                coefficient=None,
                transmission_probability=0.5,
                metadata=EstimationMetadata(
                    sample_count=len(usable), estimation_method=EstimationMethod.INSUFFICIENT_DATA,
                    estimation_window=None, standard_error=None, is_prior=True,
                ),
                comparable_observations=tuple(usable), residual_returns=residuals,
                is_insufficient_evidence=True,
            )
        coefficient = sum(
            weight * (x_value - x_mean) * (y_value - y_mean)
            for weight, x_value, y_value in zip(weights, x_values, y_values)
        ) / denominator
        intercept = y_mean - coefficient * x_mean
        squared_error = sum(
            weight * (y_value - (intercept + coefficient * x_value)) ** 2
            for weight, x_value, y_value in zip(weights, x_values, y_values)
        )
        standard_error = sqrt(squared_error / max(1, len(usable) - 2) / denominator)
        transmission_probability = sum(1 for value in residuals if abs(value) >= 0.002) / len(residuals)
        return EdgeCalibration(
            coefficient=coefficient,
            transmission_probability=transmission_probability,
            metadata=EstimationMetadata(
                sample_count=len(usable), estimation_method=EstimationMethod.OLS_REGRESSION,
                estimation_window=self._window(usable), standard_error=standard_error, is_prior=False,
            ),
            comparable_observations=tuple(usable), residual_returns=residuals,
            is_insufficient_evidence=False,
        )

    @staticmethod
    def _proximity(query_value: float | None, candidate_value: float | None) -> float:
        if query_value is None and candidate_value is None:
            return 0.5
        if query_value is None or candidate_value is None:
            return 0.35
        scale = max(abs(query_value), abs(candidate_value), 0.01)
        return max(0.0, 1.0 - abs(query_value - candidate_value) / scale)

    @staticmethod
    def _window(observations: list[WeightedObservation]) -> str:
        dates = sorted(item.observation.event_date.date().isoformat() for item in observations)
        return f"{dates[0]} to {dates[-1]}"
