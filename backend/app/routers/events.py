"""Events router — list, retrieve, and manually ingest events."""

from typing import Any
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


class IngestRequest(BaseModel):
    """Request body for manual event ingestion."""

    title: str
    description: str
    source_url: str = ""
    affected_tickers: list[str] = []


@router.get("")
async def list_events(  # type: ignore[no-untyped-def]
    category: str | None = Query(None, description="Filter by event category"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """List canonical events with optional category filter."""
    params: dict = {"limit": limit, "offset": offset}

    where_clause = ""
    if category:
        where_clause = "WHERE ce.category = :category"
        params["category"] = category

    stmt = text(f"""
        SELECT ce.id, ce.title, ce.category, ce.event_date,
               ce.market_regime_at_event, ce.vix_at_event,
               ce.affected_tickers, ce.bootstrap_status,
               COUNT(heo.id) as outcome_count
        FROM canonical_events ce
        LEFT JOIN historical_event_outcomes heo ON heo.canonical_event_id = ce.id
        {where_clause}
        GROUP BY ce.id
        ORDER BY ce.event_date DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(stmt, params)
    rows = result.mappings().all()

    return {
        "events": [dict(row) for row in rows],
        "count": len(rows),
        "offset": offset,
        "limit": limit,
    }


@router.get("/{event_id}")
async def get_event(event_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:  # noqa: B008
    """Retrieve a single canonical event with its outcomes."""
    # Fetch the event
    stmt = text("""
        SELECT id, title, description, category, event_date,
               market_regime_at_event, vix_at_event,
               affected_tickers, affected_sectors, bootstrap_status
        FROM canonical_events
        WHERE id = :event_id
    """)
    result = await db.execute(stmt, {"event_id": event_id})
    event = result.mappings().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Fetch outcomes
    outcome_stmt = text("""
        SELECT ticker, return_1d, return_3d, return_7d,
               return_14d, return_30d, return_90d,
               market_return, sector_excess_return,
               volatility_change, recovery_time_days
        FROM historical_event_outcomes
        WHERE canonical_event_id = :event_id
        ORDER BY ticker
    """)
    outcome_result = await db.execute(outcome_stmt, {"event_id": event_id})
    outcomes = [dict(row) for row in outcome_result.mappings().all()]

    # Fetch source articles
    article_stmt = text("""
        SELECT title, source_url, published_at, sentiment_score
        FROM source_articles
        WHERE canonical_event_id = :event_id
        ORDER BY published_at DESC
    """)
    article_result = await db.execute(article_stmt, {"event_id": event_id})
    articles = [dict(row) for row in article_result.mappings().all()]

    return {
        "event": dict(event),
        "outcomes": outcomes,
        "source_articles": articles,
    }


@router.post("/ingest")
async def ingest_event(  # type: ignore[no-untyped-def]
    request: IngestRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Manually ingest an event — classify, embed, and store it."""
    from app.services.ingestion_pipeline import IngestionPipeline

    pipeline = IngestionPipeline(session=db)

    try:
        # Try to set up Qdrant (non-fatal if unavailable)
        try:
            from app.vectors.store import QdrantEventStore

            pipeline.qdrant_store = QdrantEventStore()
        except Exception:
            pass

        result = await pipeline.ingest_event_text(
            title=request.title,
            description=request.description,
            source_url=request.source_url,
            affected_tickers=request.affected_tickers,
        )

        if result is None:
            return {"status": "duplicate", "message": "Event was identified as a duplicate"}

        return {"status": "ingested", "event": result}

    except Exception as e:
        logger.error(f"Event ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
