"""Event ingestion pipeline — orchestrates the full flow from raw news to stored events.

    Fetch → Deduplicate → Classify → Embed → Store → Produce
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.finnhub_rest import FinnhubRestClient
from app.intelligence.classifier import EventClassifier
from app.intelligence.dedup import DeduplicationEngine
from app.intelligence.ontology import EventOntologySchema
from app.streaming.events import EventProducer
from app.vectors.store import QdrantEventStore

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrate event ingestion from raw news to stored events."""

    TOPIC = "raw_events"

    def __init__(
        self,
        session: AsyncSession,
        qdrant_store: QdrantEventStore | None = None,
        producer: EventProducer | None = None,
        classifier: EventClassifier | None = None,
        dedup: DeduplicationEngine | None = None,
    ) -> None:
        self.session = session
        self.qdrant_store = qdrant_store
        self.producer = producer
        self.classifier = classifier or EventClassifier(use_finbert=False)
        self.dedup = dedup or DeduplicationEngine()

    async def ingest_ticker(self, ticker: str) -> list[dict[str, Any]]:
        """Fetch, classify, and store news for a single ticker.

        Returns a list of processed event dicts (skips duplicates).
        """
        # Fetch raw news
        client = FinnhubRestClient()
        try:
            news_items = await client.get_company_news(
                ticker,
                from_date=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
                to_date=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            )
        except Exception as e:
            logger.error(f"Failed to fetch news for {ticker}: {e}")
            return []

        if not news_items:
            logger.info(f"No news found for {ticker}")
            return []

        processed = []
        for article in news_items:
            try:
                result = await self._process_article(article, ticker)
                if result:
                    processed.append(result)
            except Exception as e:
                logger.error(f"Error processing article: {e}")

        logger.info(f"Processed {len(processed)} events for {ticker} "
                     f"(from {len(news_items)} articles)")
        return processed

    async def ingest_event_text(
        self,
        title: str,
        description: str,
        source_url: str = "",
        published_at: datetime | None = None,
        affected_tickers: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Classify and store a manually provided event text.

        Used by the ``POST /api/events/ingest`` endpoint and the
        forecast pipeline when a user provides raw event text.
        """
        pub_time = published_at or datetime.now(tz=timezone.utc)

        # Deduplicate
        dedup_result = self.dedup.check(source_url or title, title, description)
        if dedup_result.is_duplicate:
            logger.info(f"Duplicate event: {title}")
            return None

        # Classify
        classification = self.classifier.classify(title, description)

        # Build ontology schema
        event = EventOntologySchema(
            title=title,
            description=description,
            source_url=source_url,
            published_at=pub_time,
            event_date=pub_time,
            category=classification["category"],
            severity_score=classification["severity_score"],
            affected_tickers=affected_tickers or [],
        )

        event_id = str(uuid.uuid4())

        # Store in database
        await self._store_event(event_id, event)

        # Store in Qdrant
        if self.qdrant_store:
            try:
                await self.qdrant_store.upsert_event(
                    event_id=event_id,
                    text=f"{event.title}. {event.description}",
                    metadata={
                        "category": event.category.value,
                        "severity_score": event.severity_score,
                        "event_date": event.event_date.isoformat() if event.event_date else None,
                        "affected_tickers": event.affected_tickers,
                    },
                )
            except Exception as e:
                logger.warning(f"Qdrant upsert failed (non-fatal): {e}")

        # Produce to Redpanda
        if self.producer:
            try:
                self.producer.produce(
                    topic=self.TOPIC,
                    key=event_id,
                    value={
                        "event_id": event_id,
                        "title": event.title,
                        "category": event.category.value,
                        "severity_score": event.severity_score,
                        "published_at": event.published_at.isoformat(),
                        "affected_tickers": event.affected_tickers,
                    },
                )
            except Exception as e:
                logger.warning(f"Redpanda produce failed (non-fatal): {e}")

        return {
            "event_id": event_id,
            "title": event.title,
            "category": event.category.value,
            "severity_score": event.severity_score,
            "affected_tickers": event.affected_tickers,
        }

    async def _process_article(
        self, article: dict[str, Any], ticker: str
    ) -> dict[str, Any] | None:
        """Process a single Finnhub news article."""
        title = article.get("headline", "")
        description = article.get("summary", "")
        url = article.get("url", "")
        ts = article.get("datetime", 0)
        pub_time = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(tz=timezone.utc)

        return await self.ingest_event_text(
            title=title,
            description=description,
            source_url=url,
            published_at=pub_time,
            affected_tickers=[ticker],
        )

    async def _store_event(self, event_id: str, event: EventOntologySchema) -> None:
        """Persist an event to the events table."""
        stmt = text("""
            INSERT INTO events (
                id, title, description, source_url, published_at,
                category, severity_score, affected_tickers,
                affected_sectors, affected_countries, created_at
            ) VALUES (
                :id, :title, :description, :source_url, :published_at,
                :category, :severity_score, :tickers,
                :sectors, :countries, NOW()
            )
            ON CONFLICT (id) DO NOTHING
        """)

        await self.session.execute(stmt, {
            "id": event_id,
            "title": event.title,
            "description": event.description[:2000],
            "source_url": event.source_url[:500],
            "published_at": event.published_at,
            "category": event.category.value,
            "severity_score": event.severity_score,
            "tickers": ",".join(event.affected_tickers),
            "sectors": ",".join(event.affected_sectors),
            "countries": ",".join(event.affected_countries),
        })
        await self.session.commit()
