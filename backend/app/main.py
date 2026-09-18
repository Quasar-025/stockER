"""StockER FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan — startup and shutdown events."""
    logger.info("StockER starting up...")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"LLM Provider: Ollama @ {settings.OLLAMA_HOST}")

    # Initialize Vector DB (Qdrant)
    try:
        from app.vectors.store import QdrantEventStore
        qdrant = QdrantEventStore()
        await qdrant.ensure_collection()
        logger.info("Qdrant events collection ready")
    except Exception as e:
        logger.warning(f"Qdrant initialization failed (non-fatal): {e}")

    # Initialize Graph DB (Neo4j)
    neo4j = None
    try:
        from app.graph.client import Neo4jGraphClient
        neo4j = Neo4jGraphClient()
        await neo4j.connect()
        app.state.neo4j_client = neo4j
        logger.info("Neo4j connection ready")
    except Exception as e:
        logger.warning(f"Neo4j initialization failed (non-fatal): {e}")

    # Start Finnhub WebSocket for real-time events
    # ws_client = FinnhubWebSocketClient()
    # ws_task = asyncio.create_task(ws_client.start())

    yield

    # Shutdown logic
    logger.info("Shutting down StockER API...")
    if neo4j:
        await neo4j.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="StockER",
        description=(
            "Event-driven market intelligence platform that identifies historically "
            "similar market conditions, quantifies probable outcomes, and explains "
            "the reasoning with verifiable evidence."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check
    @app.get("/health", tags=["System"])
    async def health_check() -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "stocker-backend",
            "version": "0.1.0",
            "environment": settings.APP_ENV,
        }

    @app.get("/", tags=["System"])
    async def root() -> dict:
        """Root endpoint with API info."""
        return {
            "name": "StockER API",
            "version": "0.1.0",
            "description": "Event-Driven Market Intelligence Platform",
            "docs": "/docs",
        }

    # Register routers
    from app.routers import events, forecast, graph, health, stocks

    app.include_router(health.router)
    app.include_router(events.router)
    app.include_router(forecast.router)
    app.include_router(stocks.router)
    app.include_router(graph.router)

    return app


app = create_app()
