"""Persistent records for canonical events, outcomes, and forecast evaluation."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.database import Base


class DataSource(Base):
    """Registry of known sources and their observed operational health."""

    __tablename__ = "data_sources"

    source_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="UNAVAILABLE")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CanonicalEvent(Base):
    """Deduplicated real-world event, separate from source-article records."""

    __tablename__ = "canonical_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    estimated_disruption_magnitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_regime_at_event: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vix_at_event: Mapped[float | None] = mapped_column(Float, nullable=True)
    affected_tickers: Mapped[list[str]] = mapped_column(JSON, default=list)
    affected_sectors: Mapped[list[str]] = mapped_column(JSON, default=list)
    affected_countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    data_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # A bootstrap record may identify a candidate event but must never be used
    # as empirical calibration until sources/outcomes are verified.
    bootstrap_status: Mapped[str] = mapped_column(String(40), nullable=False, default="empirical")
    is_seeded_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceArticle(Base):
    """Raw article/filing linked to a canonical event."""

    __tablename__ = "source_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_events.id"), nullable=False, index=True
    )
    source_key: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    quality_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class HistoricalEventOutcome(Base):
    """Observed multi-horizon outcome, available only after ``available_at``."""

    __tablename__ = "historical_event_outcomes"
    __table_args__ = (UniqueConstraint("canonical_event_id", "ticker", name="uq_outcome_event_ticker"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_events.id"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    return_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_3d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_14d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_90d: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector_excess_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    volatility_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    quality_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    is_seeded_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PredictionEvaluation(Base):
    """Observed outcome for a persisted forecast and horizon."""

    __tablename__ = "prediction_evaluations"
    __table_args__ = (UniqueConstraint("forecast_id", "time_horizon_days", name="uq_eval_forecast_horizon"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forecasts.id"), nullable=False, index=True
    )
    time_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_return: Mapped[float] = mapped_column(Float, nullable=False)
    direction_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    within_prediction_interval: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
