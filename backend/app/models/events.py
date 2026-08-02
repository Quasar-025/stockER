"""Event Ontology models."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Float, func, JSON, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.utils.database import Base


class EventObject(Base):
    """Structured event ontology extracted from news/filings."""
    __tablename__ = "events"

    # Use native UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    
    # Core event data
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    # Extracted metadata (Classification & Ontology)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g., "SUPPLY_CHAIN_DISRUPTION"
    severity_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 1.0
    
    # Affected entities (JSON arrays of strings)
    affected_tickers: Mapped[list[str]] = mapped_column(JSON, default=list)
    affected_sectors: Mapped[list[str]] = mapped_column(JSON, default=list)
    affected_countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    
    # Link to Qdrant vector embedding (same UUID)
    # The actual semantic vector lives in Qdrant, we just map by ID.
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
