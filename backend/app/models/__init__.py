"""Export all models so Alembic can autogenerate migrations."""

from app.models.core import OHLCV, Stock
from app.models.events import EventObject
from app.models.forecast import Forecast
from app.models.historical import (
    CanonicalEvent,
    DataSource,
    HistoricalEventOutcome,
    PredictionEvaluation,
    SourceArticle,
)
from app.utils.database import Base

__all__ = [
    "OHLCV",
    "Base",
    "CanonicalEvent",
    "DataSource",
    "EventObject",
    "Forecast",
    "HistoricalEventOutcome",
    "PredictionEvaluation",
    "SourceArticle",
    "Stock",
]
