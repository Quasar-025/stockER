"""Event Ontology models."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.database import Base


class EventObject(Base):
    """Structured event ontology extracted from news/filings."""
    __tablename__ = "events"

    # Use native UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Multiple articles may map to one canonical event.  The foreign key is
    # intentionally not enforced here because articles can arrive before the
    # canonicalisation worker has created its parent record.
    canonical_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Core event data
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Extracted metadata (Classification & Ontology)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g., "SUPPLY_CHAIN_DISRUPTION"
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    severity_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 1.0
    estimated_disruption_magnitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_duration_days: Mapped[int | None] = mapped_column(nullable=True)
    market_regime_at_event: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vix_at_event: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Affected entities (JSON arrays of strings)
    affected_tickers: Mapped[list[str]] = mapped_column(JSON, default=list)
    affected_sectors: Mapped[list[str]] = mapped_column(JSON, default=list)
    affected_countries: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Provenance is needed for point-in-time historical evaluation.
    data_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Link to Qdrant vector embedding (same UUID)
    # The actual semantic vector lives in Qdrant, we just map by ID.

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
