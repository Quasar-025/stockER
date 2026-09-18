"""In-memory outcome tracker; persistence can mirror these records later."""

from dataclasses import dataclass, field

from app.evaluation.metrics import PredictionRecord


@dataclass
class EvaluationTracker:
    """Stores predictions without merging their probability and confidence."""

    records: list[PredictionRecord] = field(default_factory=list)

    def record(self, prediction: PredictionRecord) -> None:
        self.records.append(prediction)

    def for_model(self, model_name: str) -> list[PredictionRecord]:
        return [record for record in self.records if record.model_name == model_name]
