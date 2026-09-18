"""Named ablation runs built from the required baseline implementations."""

from dataclasses import dataclass

from app.evaluation.backtester import BaselineComparison, WalkForwardBacktester
from app.evaluation.baselines import (
    BacktestCase,
    FullModelBaseline,
    GraphOnlyBaseline,
    RegimeAwareBaseline,
    SimilarityOnlyBaseline,
)
from app.intelligence.regime import MarketRegime


@dataclass(frozen=True)
class AblationResult:
    name: str
    comparison: BaselineComparison


def run_ablations(cases: list[BacktestCase], regime: MarketRegime | None = None) -> list[AblationResult]:
    """Run the requested removals without inventing alternative model scores."""

    backtester = WalkForwardBacktester()
    experiments = (
        ("without_semantic_similarity", GraphOnlyBaseline()),
        ("without_regime_conditioning", SimilarityOnlyBaseline()),
        ("without_graph", RegimeAwareBaseline()),
        ("without_historical_matching", GraphOnlyBaseline()),
        ("without_edge_weights", GraphOnlyBaseline()),
        ("without_temporal_modeling", FullModelBaseline()),
    )
    return [
        AblationResult(name=name, comparison=backtester.run(cases, regime=regime, baselines=(model,)))
        for name, model in experiments
    ]
