"""System health endpoint — checks database, Qdrant, Neo4j, Redis connectivity."""

from typing import Any
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:  # noqa: B008
    """Check overall system health and component connectivity."""
    status = {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "components": {},
    }

    # PostgreSQL / TimescaleDB
    try:
        await db.execute(text("SELECT 1"))
        status["components"]["database"] = {"status": "healthy"}  # type: ignore[index]
    except Exception as e:
        status["components"]["database"] = {"status": "unhealthy", "error": str(e)}  # type: ignore[index]
        status["status"] = "degraded"

    # Redis
    try:
        import redis

        r = redis.Redis(host="localhost", port=6379, socket_timeout=2)
        r.ping()
        status["components"]["redis"] = {"status": "healthy"}  # type: ignore[index]
    except Exception as e:
        status["components"]["redis"] = {"status": "unhealthy", "error": str(e)}  # type: ignore[index]
        status["status"] = "degraded"

    # Qdrant
    try:
        from qdrant_client import QdrantClient

        qc = QdrantClient(host="localhost", port=6333, timeout=2)
        qc.get_collections()
        status["components"]["qdrant"] = {"status": "healthy"}  # type: ignore[index]
    except Exception as e:
        status["components"]["qdrant"] = {"status": "unhealthy", "error": str(e)}  # type: ignore[index]
        status["status"] = "degraded"

    # Neo4j
    try:
        from app.graph.client import Neo4jGraphClient

        neo4j = Neo4jGraphClient()
        healthy = await neo4j.healthcheck()
        await neo4j.close()
        status["components"]["neo4j"] = {"status": "healthy" if healthy else "unhealthy"}  # type: ignore[index]
        if not healthy:
            status["status"] = "degraded"
    except Exception as e:
        status["components"]["neo4j"] = {"status": "unhealthy", "error": str(e)}  # type: ignore[index]
        status["status"] = "degraded"

    return status


@router.get("/sources")
async def data_source_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:  # noqa: B008
    """Return data source freshness and counts."""
    sources = {}

    # Stocks count
    try:
        result = await db.execute(text("SELECT COUNT(*) as cnt FROM stocks"))
        row = result.mappings().first()
        sources["stocks"] = {"count": row["cnt"] if row else 0}
    except Exception:
        sources["stocks"] = {"count": 0, "error": "table may not exist"}

    # OHLCV freshness
    try:
        result = await db.execute(text("SELECT COUNT(*) as cnt, MAX(time) as latest FROM ohlcv"))
        row = result.mappings().first()
        sources["ohlcv"] = {
            "count": row["cnt"] if row else 0,
            "latest": str(row["latest"]) if row and row["latest"] else None,
        }
    except Exception:
        sources["ohlcv"] = {"count": 0, "error": "table may not exist"}

    # Events count
    try:
        result = await db.execute(text("SELECT COUNT(*) as cnt FROM events"))
        row = result.mappings().first()
        sources["events"] = {"count": row["cnt"] if row else 0}
    except Exception:
        sources["events"] = {"count": 0, "error": "table may not exist"}

    # Canonical events
    try:
        result = await db.execute(text("SELECT COUNT(*) as cnt FROM canonical_events"))
        row = result.mappings().first()
        sources["canonical_events"] = {"count": row["cnt"] if row else 0}
    except Exception:
        sources["canonical_events"] = {"count": 0, "error": "table may not exist"}

    # Historical outcomes
    try:
        result = await db.execute(text("SELECT COUNT(*) as cnt FROM historical_event_outcomes"))
        row = result.mappings().first()
        sources["historical_outcomes"] = {"count": row["cnt"] if row else 0}
    except Exception:
        sources["historical_outcomes"] = {"count": 0, "error": "table may not exist"}

    return {"sources": sources}
