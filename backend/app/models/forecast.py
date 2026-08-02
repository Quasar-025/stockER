"""Forecast and Prediction models."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Float, func, JSON, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.utils.database import Base


class Forecast(Base):
    """Output of the Market Impact Engine, tracking predictions over time."""
    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    
    # The event that triggered this forecast
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Target entity
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    # The prediction
    predicted_impact: Mapped[float] = mapped_column(Float, nullable=False)  # e.g., -0.05 for -5% drop
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 1.0
    time_horizon_days: Mapped[int] = mapped_column(nullable=False)
    
    # The underlying data explaining *why* (passed to LLM)
    similar_historical_events: Mapped[list[dict]] = mapped_column(JSON, default=list)
    causal_chain: Mapped[list[str]] = mapped_column(JSON, default=list)
    market_regime: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Evaluation tracking (populated later during continuous eval)
    actual_impact: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
