"""Core financial models (Stocks and Price Data)."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.database import Base


class Stock(Base):
    """A publicly traded company / asset."""

    __tablename__ = "stocks"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    exchange: Mapped[str | None] = mapped_column(String(100))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OHLCV(Base):
    """Time-series price data (Open, High, Low, Close, Volume).

    This table will be converted to a TimescaleDB hypertable in Alembic migrations.
    """

    __tablename__ = "ohlcv"

    # Composite primary key for TimescaleDB (time + partition key)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)

    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (Index("ix_ohlcv_ticker_time", "ticker", "time", unique=True),)
