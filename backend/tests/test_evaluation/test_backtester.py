from datetime import datetime, timedelta, timezone

from app.evaluation.backtester import WalkForwardBacktester
from app.evaluation.baselines import BacktestCase, HistoricalCandidate
from app.evaluation.metrics import DEPTH_BUCKETS
from app.intelligence.regime import MarketRegime


def _case(depth: int) -> BacktestCase:
    as_of = datetime(2024, 4, 3, tzinfo=timezone.utc)
    return BacktestCase(
        case_id=f"case-{depth}", as_of=as_of, ticker="NVDA", actual_return=-0.02,
        propagation_depth=depth, horizon_days=7, market_return=-0.01,
        historical_candidates=(
            HistoricalCandidate(as_of - timedelta(days=200), as_of - timedelta(days=100), -0.03, MarketRegime.BEAR_HIGH_VOL, 0.9),
            HistoricalCandidate(as_of + timedelta(days=1), as_of + timedelta(days=2), 0.50, MarketRegime.BEAR_HIGH_VOL, 0.99),
        ),
        graph_returns=(-0.025, -0.01, -0.02, -0.03, -0.02, -0.01),
    )


def test_all_baselines_produce_results_at_all_depths() -> None:
    comparison = WalkForwardBacktester().run([_case(1), _case(2), _case(3), _case(4)], regime=MarketRegime.BEAR_HIGH_VOL)

    assert set(comparison.predictions) == {
        "market_only", "similarity_only", "regime_aware_similarity", "graph_only", "full_model"
    }
    assert all(set(depth_metrics) == set(DEPTH_BUCKETS) for depth_metrics in comparison.metrics_by_model_and_depth.values())


def test_walk_forward_excludes_future_historical_candidates() -> None:
    comparison = WalkForwardBacktester().run([_case(1)], regime=MarketRegime.BEAR_HIGH_VOL)
    similarity = comparison.predictions["similarity_only"][0]

    assert similarity.predicted_return == -0.03
