"""Forecast metrics, always stratified by propagation depth."""

from dataclasses import dataclass
from math import sqrt

DEPTH_BUCKETS: tuple[int | str, ...] = (1, 2, 3, "4+")


def depth_bucket(depth: int) -> int | str:
    return depth if depth in {1, 2, 3} else "4+"


@dataclass(frozen=True)
class PredictionRecord:
    model_name: str
    ticker: str
    propagation_depth: int
    predicted_return: float
    actual_return: float
    direction_probability: float
    predicted_direction: str
    return_range: tuple[float, float]
    horizon_days: int
    entity_identified: bool = True
    actual_entity_affected: bool = True

    @property
    def predicted_positive_probability(self) -> float:
        if self.predicted_direction == "BULLISH":
            return self.direction_probability
        if self.predicted_direction == "BEARISH":
            return 1.0 - self.direction_probability
        return 0.5


@dataclass(frozen=True)
class MetricSummary:
    sample_count: int
    directional_accuracy: float | None
    mae: float | None
    rmse: float | None
    brier_score: float | None
    calibration_error: float | None
    precision: float | None
    recall: float | None
    f1: float | None
    prediction_interval_coverage: float | None
    average_interval_width: float | None
    propagation_precision: float | None
    propagation_recall: float | None


def calculate_metrics(records: list[PredictionRecord]) -> MetricSummary:
    """Calculate outcome, calibration, interval, and entity metrics honestly."""

    if not records:
        return MetricSummary(0, *(None for _ in range(12)))
    direction_correct = [
        (record.predicted_return >= 0) == (record.actual_return >= 0) for record in records
    ]
    errors = [record.predicted_return - record.actual_return for record in records]
    brier_terms = [
        (record.predicted_positive_probability - float(record.actual_return >= 0)) ** 2
        for record in records
    ]
    calibration = _calibration_error(records)
    covered = [
        record.return_range[0] <= record.actual_return <= record.return_range[1]
        for record in records
    ]
    widths = [record.return_range[1] - record.return_range[0] for record in records]
    tp = sum(record.entity_identified and record.actual_entity_affected for record in records)
    fp = sum(record.entity_identified and not record.actual_entity_affected for record in records)
    fn = sum(not record.entity_identified and record.actual_entity_affected for record in records)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return MetricSummary(
        sample_count=len(records),
        directional_accuracy=sum(direction_correct) / len(records),
        mae=sum(abs(error) for error in errors) / len(errors),
        rmse=sqrt(sum(error**2 for error in errors) / len(errors)),
        brier_score=sum(brier_terms) / len(brier_terms),
        calibration_error=calibration,
        precision=precision,
        recall=recall,
        f1=f1,
        prediction_interval_coverage=sum(covered) / len(covered),
        average_interval_width=sum(widths) / len(widths),
        propagation_precision=precision,
        propagation_recall=recall,
    )


def metrics_by_depth(records: list[PredictionRecord]) -> dict[int | str, MetricSummary]:
    """Always return all required depth buckets, including zero-sample ones."""

    grouped: dict[int | str, list[PredictionRecord]] = {bucket: [] for bucket in DEPTH_BUCKETS}
    for record in records:
        grouped[depth_bucket(record.propagation_depth)].append(record)
    return {bucket: calculate_metrics(bucket_records) for bucket, bucket_records in grouped.items()}


def _calibration_error(records: list[PredictionRecord]) -> float:
    bins: dict[int, list[PredictionRecord]] = {}
    for record in records:
        bucket = min(9, int(record.predicted_positive_probability * 10))
        bins.setdefault(bucket, []).append(record)
    return sum(
        len(bucket_records)
        / len(records)
        * abs(
            sum(record.predicted_positive_probability for record in bucket_records)
            / len(bucket_records)
            - sum(record.actual_return >= 0 for record in bucket_records) / len(bucket_records)
        )
        for bucket_records in bins.values()
    )
