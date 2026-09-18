"""The five required baseline estimators for causal-cascade evaluation."""

from dataclasses import dataclass, field
from datetime import datetime

from app.intelligence.distribution import EmpiricalImpactDistribution
from app.intelligence.regime import MarketRegime


@dataclass(frozen=True)
class HistoricalCandidate:
    event_date: datetime
    available_at: datetime
    return_value: float
    regime: MarketRegime
    similarity_score: float


@dataclass(frozen=True)
class BacktestCase:
    case_id: str
    as_of: datetime
    ticker: str
    actual_return: float
    propagation_depth: int
    horizon_days: int
    market_return: float
    historical_candidates: tuple[HistoricalCandidate, ...] = ()
    graph_returns: tuple[float, ...] = ()
    graph_temporal_approximation: bool = False

    def point_in_time_candidates(self) -> tuple[HistoricalCandidate, ...]:
        return tuple(
            candidate for candidate in self.historical_candidates
            if candidate.event_date < self.as_of and candidate.available_at <= self.as_of
        )


@dataclass(frozen=True)
class BaselinePrediction:
    model_name: str
    expected_return: float
    direction_probability: float
    predicted_direction: str
    return_range: tuple[float, float]
    sample_count: int
    insufficient_evidence: bool


class _BaseBaseline:
    name = "base"

    def _from_returns(self, returns: tuple[float, ...] | list[float]) -> BaselinePrediction:
        distribution = EmpiricalImpactDistribution.from_returns(returns)
        probabilities = {
            "BULLISH": distribution.probability_positive,
            "BEARISH": distribution.probability_negative,
            "NEUTRAL": distribution.probability_neutral,
        }
        direction, probability = max(probabilities.items(), key=lambda item: item[1])
        return BaselinePrediction(
            model_name=self.name, expected_return=distribution.mean_return, direction_probability=probability,
            predicted_direction=direction if distribution.sample_count else "UNCERTAIN",
            return_range=(distribution.quantiles.p25, distribution.quantiles.p75),
            sample_count=distribution.sample_count, insufficient_evidence=distribution.sample_count <= 5,
        )


class MarketOnlyBaseline(_BaseBaseline):
    """Baseline 1: predict observed market return for each entity."""

    name = "market_only"

    def predict(self, case: BacktestCase, regime: MarketRegime | None = None) -> BaselinePrediction:
        return self._from_returns((case.market_return,))


class SimilarityOnlyBaseline(_BaseBaseline):
    """Baseline 2: historical event similarity without graph or regime filter."""

    name = "similarity_only"

    def predict(self, case: BacktestCase, regime: MarketRegime | None = None) -> BaselinePrediction:
        candidates = case.point_in_time_candidates()
        return self._from_returns(tuple(candidate.return_value for candidate in candidates))


class RegimeAwareBaseline(_BaseBaseline):
    """Baseline 3: historical similarity restricted to the current regime."""

    name = "regime_aware_similarity"

    def predict(self, case: BacktestCase, regime: MarketRegime | None = None) -> BaselinePrediction:
        candidates = case.point_in_time_candidates()
        if regime is not None:
            candidates = tuple(candidate for candidate in candidates if candidate.regime == regime)
        return self._from_returns(tuple(candidate.return_value for candidate in candidates))


class GraphOnlyBaseline(_BaseBaseline):
    """Baseline 4: propagation outcomes without historical similarity matching."""

    name = "graph_only"

    def predict(self, case: BacktestCase, regime: MarketRegime | None = None) -> BaselinePrediction:
        if case.graph_temporal_approximation:
            return self._from_returns(())
        return self._from_returns(case.graph_returns)


class FullModelBaseline(_BaseBaseline):
    """Baseline 5: point-in-time regime-aware similarity plus graph evidence."""

    name = "full_model"

    def predict(self, case: BacktestCase, regime: MarketRegime | None = None) -> BaselinePrediction:
        similarity = RegimeAwareBaseline().predict(case, regime)
        graph = GraphOnlyBaseline().predict(case, regime)
        sources = [source for source in (similarity, graph) if source.sample_count]
        if not sources:
            return self._from_returns(())
        # Evidence-count weighting does not prescribe direction; it only pools
        # independently observed historical samples for this baseline.
        expected = sum(source.expected_return * source.sample_count for source in sources) / sum(source.sample_count for source in sources)
        range_low = sum(source.return_range[0] * source.sample_count for source in sources) / sum(source.sample_count for source in sources)
        range_high = sum(source.return_range[1] * source.sample_count for source in sources) / sum(source.sample_count for source in sources)
        best = max(sources, key=lambda source: source.direction_probability)
        return BaselinePrediction(
            model_name=self.name, expected_return=expected, direction_probability=best.direction_probability,
            predicted_direction=best.predicted_direction, return_range=(range_low, range_high),
            sample_count=sum(source.sample_count for source in sources),
            insufficient_evidence=any(source.insufficient_evidence for source in sources),
        )


def required_baselines() -> tuple[_BaseBaseline, ...]:
    return (
        MarketOnlyBaseline(), SimilarityOnlyBaseline(), RegimeAwareBaseline(),
        GraphOnlyBaseline(), FullModelBaseline(),
    )
