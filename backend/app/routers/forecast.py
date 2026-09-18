"""Forecast router — generate new forecasts or retrieve existing ones."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


class ForecastRequest(BaseModel):
    """Request body for generating a new forecast."""

    title: str
    description: str
    affected_tickers: list[str] = []


@router.post("")
async def generate_forecast(
    request: ForecastRequest,
    fastapi_req: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Run the intelligence pipeline to forecast market impact."""
    from app.services.forecast_pipeline import ForecastPipeline

    neo4j_client = getattr(fastapi_req.app.state, "neo4j_client", None)
    if not neo4j_client:
        neo4j_client = getattr(fastapi_req.app.state, "neo4j", None)

    if not neo4j_client:
        # Lazy initialization if it failed during startup
        from app.graph.client import Neo4jGraphClient

        try:
            neo4j_client = Neo4jGraphClient()
            fastapi_req.app.state.neo4j_client = neo4j_client
            logger.info("Lazy-initialized Neo4j client")
        except Exception as e:
            logger.warning(f"Lazy Neo4j initialization failed: {e}")

    pipeline = ForecastPipeline(session=db, neo4j_client=neo4j_client)

    try:
        # Try to set up Qdrant (non-fatal if unavailable)
        try:
            from app.vectors.store import QdrantEventStore

            pipeline.qdrant_store = QdrantEventStore()
        except Exception:
            pass

        result = await pipeline.forecast_from_text(
            title=request.title,
            description=request.description,
            affected_tickers=request.affected_tickers,
        )

        return result

    except Exception as e:
        logger.error(f"Forecast generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/history")
async def list_forecasts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """List previously generated forecasts."""
    stmt = text("""
        SELECT id, event_title, event_category, event_severity, created_at
        FROM forecasts
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(stmt, {"limit": limit, "offset": offset})
    rows = result.mappings().all()

    return {
        "forecasts": [dict(row) for row in rows],
        "count": len(rows),
        "offset": offset,
        "limit": limit,
    }


@router.get("/{forecast_id}")
async def get_forecast(forecast_id: str, db: AsyncSession = Depends(get_db)):  # noqa: B008
    """Retrieve a specific generated forecast by ID."""
    stmt = text("""
        SELECT id, event_title, event_category, event_severity,
               forecasts_json, explanation, created_at
        FROM forecasts
        WHERE id = :forecast_id
    """)

    result = await db.execute(stmt, {"forecast_id": forecast_id})
    forecast = result.mappings().first()

    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")

    import json

    response = dict(forecast)
    if isinstance(response.get("forecasts_json"), str):
        response["forecasts_json"] = json.loads(response["forecasts_json"])

    return {"forecast": response}
