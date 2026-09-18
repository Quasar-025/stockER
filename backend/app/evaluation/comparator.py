"""Convert v2 entity forecasts plus observed outcomes into metric records."""

from app.evaluation.metrics import PredictionRecord
from app.schemas.forecast import EntityImpact


class ForecastComparator:
    """Compares returned forecast objects with actual horizon returns."""

    @staticmethod
    def compare(model_name: str, impact: EntityImpact, actual_return: float) -> PredictionRecord:
        return PredictionRecord(
            model_name=model_name, ticker=impact.ticker, propagation_depth=impact.propagation_depth,
            predicted_return=impact.expected_return, actual_return=actual_return,
            direction_probability=impact.direction_probability, predicted_direction=impact.direction.value,
            return_range=impact.return_range, horizon_days=impact.time_horizon_days,
        )
