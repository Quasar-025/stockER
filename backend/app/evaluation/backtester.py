"""Point-in-time walk-forward backtesting and mandatory baseline comparison."""

from dataclasses import dataclass
from datetime import datetime

from app.evaluation.baselines import (
    BacktestCase,
    BaselinePrediction,
    _BaseBaseline,
    required_baselines,
)
from app.evaluation.metrics import MetricSummary, PredictionRecord, metrics_by_depth
from app.intelligence.regime import MarketRegime


@dataclass(frozen=True)
class BaselineComparison:
    predictions: dict[str, list[PredictionRecord]]
    metrics_by_model_and_depth: dict[str, dict[int | str, MetricSummary]]


class WalkForwardBacktester:
    """Evaluates each dated case using only data knowable at that date."""

    def run(
        self,
        cases: list[BacktestCase],
        *,
        regime: MarketRegime | None = None,
        baselines: tuple[_BaseBaseline, ...] | None = None,
    ) -> BaselineComparison:
        models = baselines or required_baselines()
        records: dict[str, list[PredictionRecord]] = {model.name: [] for model in models}
        for case in sorted(cases, key=lambda item: item.as_of):
            for model in models:
                prediction = model.predict(case, regime)
                records[model.name].append(self._record(case, prediction))
        return BaselineComparison(
            predictions=records,
            metrics_by_model_and_depth={name: metrics_by_depth(values) for name, values in records.items()},
        )

    def rolling_window(
        self, cases: list[BacktestCase], window_start: datetime, window_end: datetime, *, regime: MarketRegime | None = None
    ) -> BaselineComparison:
        return self.run([case for case in cases if window_start <= case.as_of <= window_end], regime=regime)

    def out_of_time(
        self, cases: list[BacktestCase], holdout_start: datetime, *, regime: MarketRegime | None = None
    ) -> BaselineComparison:
        return self.run([case for case in cases if case.as_of >= holdout_start], regime=regime)

    @staticmethod
    def _record(case: BacktestCase, prediction: BaselinePrediction) -> PredictionRecord:
        return PredictionRecord(
            model_name=prediction.model_name, ticker=case.ticker, propagation_depth=case.propagation_depth,
            predicted_return=prediction.expected_return, actual_return=case.actual_return,
            direction_probability=prediction.direction_probability, predicted_direction=prediction.predicted_direction,
            return_range=prediction.return_range, horizon_days=case.horizon_days,
        )
