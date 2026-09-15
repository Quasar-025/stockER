"""Initial reproducible StockER v2 schema.

Revision ID: 20260910_0001
Revises:
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260910_0001"
down_revision = None
branch_labels = None
depends_on = None


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "stocks",
        sa.Column("ticker", sa.String(length=20), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sector", sa.String(length=100)),
        sa.Column("industry", sa.String(length=100)),
        sa.Column("country", sa.String(length=100)),
        sa.Column("exchange", sa.String(length=100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "ohlcv",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("ticker", sa.String(length=20), primary_key=True),
        sa.Column("open", sa.Float(), nullable=False), sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False), sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_ohlcv_ticker_time", "ohlcv", ["ticker", "time"], unique=True)
    op.execute("SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE)")
    op.create_table(
        "data_sources",
        sa.Column("source_key", sa.String(length=100), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True)), sa.Column("freshness_seconds", sa.Float()),
        sa.Column("notes", sa.String()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "canonical_events",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(length=500), nullable=False), sa.Column("description", sa.String(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False), sa.Column("subcategory", sa.String(length=100)),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_disruption_magnitude", sa.Float()), sa.Column("estimated_duration_days", sa.Integer()),
        sa.Column("market_regime_at_event", sa.String(length=50)), sa.Column("vix_at_event", sa.Float()),
        sa.Column("affected_tickers", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("affected_sectors", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("affected_countries", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("data_source", sa.String(length=100)), sa.Column("source_timestamp", sa.DateTime(timezone=True)),
        sa.Column("ingested_at", sa.DateTime(timezone=True)), sa.Column("bootstrap_status", sa.String(length=40), nullable=False),
        sa.Column("is_seeded_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_canonical_events_category", "canonical_events", ["category"])
    op.create_index("ix_canonical_events_event_date", "canonical_events", ["event_date"])
    op.create_table(
        "events",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("canonical_event_id", _uuid()), sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(), nullable=False), sa.Column("source_url", sa.String(length=1000), nullable=False, unique=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False), sa.Column("event_date", sa.DateTime(timezone=True)),
        sa.Column("category", sa.String(length=100), nullable=False), sa.Column("subcategory", sa.String(length=100)),
        sa.Column("severity_score", sa.Float(), nullable=False), sa.Column("estimated_disruption_magnitude", sa.Float()),
        sa.Column("estimated_duration_days", sa.Integer()), sa.Column("market_regime_at_event", sa.String(length=50)),
        sa.Column("vix_at_event", sa.Float()), sa.Column("affected_tickers", sa.JSON()),
        sa.Column("affected_sectors", sa.JSON()), sa.Column("affected_countries", sa.JSON()),
        sa.Column("data_source", sa.String(length=100)), sa.Column("source_timestamp", sa.DateTime(timezone=True)),
        sa.Column("ingested_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    for name, column in (("canonical_event_id", "canonical_event_id"), ("published_at", "published_at"), ("event_date", "event_date"), ("category", "category"), ("subcategory", "subcategory")):
        op.create_index(f"ix_events_{name}", "events", [column])
    op.create_table(
        "source_articles",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("canonical_event_id", _uuid(), sa.ForeignKey("canonical_events.id"), nullable=False),
        sa.Column("source_key", sa.String(length=100), nullable=False), sa.Column("source_url", sa.String(length=1000), nullable=False, unique=True),
        sa.Column("title", sa.String(length=500), nullable=False), sa.Column("content", sa.String()),
        sa.Column("published_at", sa.DateTime(timezone=True)), sa.Column("source_timestamp", sa.DateTime(timezone=True)),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()")), sa.Column("quality_metadata", sa.JSON()),
    )
    op.create_index("ix_source_articles_canonical_event_id", "source_articles", ["canonical_event_id"])
    op.create_table(
        "historical_event_outcomes",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("canonical_event_id", _uuid(), sa.ForeignKey("canonical_events.id"), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        *[sa.Column(f"return_{horizon}d", sa.Float()) for horizon in (1, 3, 7, 14, 30, 90)],
        sa.Column("market_return", sa.Float()), sa.Column("sector_excess_return", sa.Float()), sa.Column("volatility_change", sa.Float()),
        sa.Column("volume_change", sa.Float()), sa.Column("recovery_time_days", sa.Integer()),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False), sa.Column("quality_metadata", sa.JSON()),
        sa.Column("is_seeded_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("canonical_event_id", "ticker", name="uq_outcome_event_ticker"),
    )
    op.create_index("ix_historical_event_outcomes_canonical_event_id", "historical_event_outcomes", ["canonical_event_id"])
    op.create_index("ix_historical_event_outcomes_ticker", "historical_event_outcomes", ["ticker"])
    op.create_index("ix_historical_event_outcomes_available_at", "historical_event_outcomes", ["available_at"])
    op.create_table(
        "forecasts",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")), sa.Column("event_id", _uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False), sa.Column("predicted_impact", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False), sa.Column("model_confidence", sa.Float()), sa.Column("direction", sa.String(length=20)),
        sa.Column("direction_probability", sa.Float()), sa.Column("probability_positive", sa.Float()), sa.Column("probability_negative", sa.Float()), sa.Column("probability_neutral", sa.Float()),
        sa.Column("return_p25", sa.Float()), sa.Column("return_p50", sa.Float()), sa.Column("return_p75", sa.Float()), sa.Column("time_horizon_days", sa.Integer(), nullable=False),
        sa.Column("propagation_depth", sa.Integer()), sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("insufficient_evidence", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("similar_historical_events", sa.JSON()), sa.Column("causal_chain", sa.JSON()), sa.Column("market_regime", sa.String(length=50), nullable=False),
        sa.Column("effect_decomposition", sa.JSON()), sa.Column("supporting_evidence", sa.JSON()), sa.Column("contradicting_evidence", sa.JSON()), sa.Column("estimation_metadata", sa.JSON()),
        sa.Column("actual_impact", sa.Float()), sa.Column("evaluation_score", sa.Float()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_forecasts_event_id", "forecasts", ["event_id"])
    op.create_index("ix_forecasts_ticker", "forecasts", ["ticker"])
    op.create_table(
        "prediction_evaluations",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("forecast_id", _uuid(), sa.ForeignKey("forecasts.id"), nullable=False), sa.Column("time_horizon_days", sa.Integer(), nullable=False),
        sa.Column("actual_return", sa.Float(), nullable=False), sa.Column("direction_correct", sa.Boolean()), sa.Column("within_prediction_interval", sa.Boolean()),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("forecast_id", "time_horizon_days", name="uq_eval_forecast_horizon"),
    )
    op.create_index("ix_prediction_evaluations_forecast_id", "prediction_evaluations", ["forecast_id"])


def downgrade() -> None:
    for table in ("prediction_evaluations", "forecasts", "historical_event_outcomes", "source_articles", "events", "canonical_events", "data_sources", "ohlcv", "stocks"):
        op.drop_table(table)
