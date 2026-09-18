from datetime import UTC, datetime

from app.evaluation.backtester import WalkForwardBacktester
from app.evaluation.baselines import BacktestCase
from app.intelligence.regime import MarketRegime


def test_all_five_baselines_and_depth_buckets_run() -> None:
    case = BacktestCase("tsmc", datetime(2024, 4, 3, tzinfo=UTC), "NVDA", -.02, 4, 30, -.01)
    result = WalkForwardBacktester().run([case], regime=MarketRegime.BEAR_HIGH_VOL)
    assert len(result.predictions) == 5
    assert "4+" in result.metrics_by_model_and_depth["full_model"]
