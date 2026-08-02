"""StockER FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
import logging

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

    # TODO: Initialize database connections
    # TODO: Initialize Qdrant client
    # TODO: Initialize Neo4j client
    # TODO: Initialize Redpanda consumers
    # TODO: Start background ingestion tasks

    yield

    # Shutdown
    logger.info("StockER shutting down...")
    # TODO: Close database connections
    # TODO: Close Qdrant client
    # TODO: Close Neo4j client
    # TODO: Stop Redpanda consumers


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

    # TODO: Include routers
    # app.include_router(stocks_router, prefix="/api/stocks", tags=["Stocks"])
    # app.include_router(events_router, prefix="/api/events", tags=["Events"])
    # app.include_router(predictions_router, prefix="/api/predict", tags=["Predictions"])
    # app.include_router(portfolio_router, prefix="/api/portfolio", tags=["Portfolio"])
    # app.include_router(evaluation_router, prefix="/api/evaluation", tags=["Evaluation"])
    # app.include_router(ws_router, prefix="/ws", tags=["WebSocket"])

    return app


app = create_app()
