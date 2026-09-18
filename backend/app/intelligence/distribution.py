"""Empirical outcome summaries used by the probabilistic forecast layer."""

from math import sqrt
from statistics import mean, pstdev

from pydantic import BaseModel, Field


class ImpactQuantileSummary(BaseModel):
    """Finite-sample quantile summary, explicitly not a full distribution."""

    p25: float
    p50: float
    p75: float


class EmpiricalImpactDistribution(BaseModel):
    """Empirical outcome probabilities and quantile summaries.

    It represents the observed finite sample; p25/p50/p75 are named
    separately so callers cannot mistake three numbers for a parametric return
    distribution.
    """

    mean_return: float
    quantiles: ImpactQuantileSummary
    probability_positive: float = Field(ge=0.0, le=1.0)
    probability_negative: float = Field(ge=0.0, le=1.0)
    probability_neutral: float = Field(ge=0.0, le=1.0)
    historical_consistency: float = Field(ge=0.0, le=1.0)
    sample_count: int = Field(ge=0)
    standard_error: float | None = Field(default=None, ge=0.0)
    is_prior: bool = False

    @classmethod
    def from_returns(
        cls, returns: list[float] | tuple[float, ...], *, neutral_band: float = 0.001
    ) -> "EmpiricalImpactDistribution":
        """Summarize observed returns, using a direction-neutral empty prior."""

        values = sorted(float(value) for value in returns)
        if not values:
            return cls(
                mean_return=0.0, quantiles=ImpactQuantileSummary(p25=0.0, p50=0.0, p75=0.0),
                probability_positive=0.5, probability_negative=0.5, probability_neutral=0.0,
                historical_consistency=0.0, sample_count=0, standard_error=None, is_prior=True,
            )
        average = mean(values)
        positive = sum(value > neutral_band for value in values) / len(values)
        negative = sum(value < -neutral_band for value in values) / len(values)
        neutral = 1.0 - positive - negative
        dominant_direction = max(positive, negative, neutral)
        return cls(
            mean_return=average,
            quantiles=ImpactQuantileSummary(
                p25=cls._quantile(values, 0.25), p50=cls._quantile(values, 0.50), p75=cls._quantile(values, 0.75)
            ),
            probability_positive=positive, probability_negative=negative, probability_neutral=neutral,
            historical_consistency=dominant_direction,
            sample_count=len(values),
            standard_error=(pstdev(values) / sqrt(len(values))) if len(values) > 1 else None,
        )

    @staticmethod
    def _quantile(sorted_values: list[float], percentile: float) -> float:
        if len(sorted_values) == 1:
            return sorted_values[0]
        position = (len(sorted_values) - 1) * percentile
        lower = int(position)
        upper = min(lower + 1, len(sorted_values) - 1)
        fraction = position - lower
        return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


# Compatibility-facing name for callers of the implementation plan.  The
# concrete type still calls its quantiles summaries, never a full distribution.
ImpactDistribution = EmpiricalImpactDistribution
