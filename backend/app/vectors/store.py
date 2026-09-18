"""Qdrant vector store for event embeddings and semantic similarity search.

Events are stored as points in a ``stocker_events`` collection.  Each point
carries the full ``EventOntologySchema`` metadata so the Similarity Engine
can run hybrid scoring (semantic + structured) in a single query path.
"""

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient, models

from app.config import settings
from app.vectors.embedding import EmbeddingService

logger = logging.getLogger(__name__)

COLLECTION_NAME = "stocker_events"


class QdrantEventStore:
    """Manages event embeddings in Qdrant."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        client: QdrantClient | None = None,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.client = client or QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )

    async def ensure_collection(self) -> None:
        """Create the events collection if it doesn't already exist."""
        collections = self.client.get_collections().collections
        names = {c.name for c in collections}

        if COLLECTION_NAME not in names:
            dimension = self.embedding_service.dimension
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=dimension,
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection '{COLLECTION_NAME}' (dim={dimension}, cosine)")
        else:
            logger.debug(f"Qdrant collection '{COLLECTION_NAME}' already exists")

    async def upsert_event(
        self,
        event_id: str | uuid.UUID,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Embed *text* and upsert the vector with *metadata* into Qdrant."""
        vector = await self.embedding_service.embed_text(text)
        point_id = str(event_id)

        payload = metadata or {}
        payload["text_preview"] = text[:500]

        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )
        logger.debug(f"Upserted event {point_id} into Qdrant")

    async def upsert_events_batch(
        self,
        items: list[tuple[str | uuid.UUID, str, dict[str, Any]]],
    ) -> int:
        """Batch upsert: each item is ``(event_id, text, metadata)``."""
        if not items:
            return 0

        texts = [text for _, text, _ in items]
        vectors = await self.embedding_service.embed_batch(texts)

        points = []
        for (event_id, text, metadata), vector in zip(items, vectors, strict=False):
            payload = metadata or {}
            payload["text_preview"] = text[:500]
            points.append(
                models.PointStruct(
                    id=str(event_id),
                    vector=vector,
                    payload=payload,
                )
            )

        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )
        logger.info(f"Batch upserted {len(points)} events into Qdrant")
        return len(points)

    async def search_similar(
        self,
        text: str,
        top_k: int = 20,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Embed *text* and return the nearest events.

        Returns ``[(event_id, cosine_score, payload), ...]``.
        """
        vector = await self.embedding_service.embed_text(text)
        return await self.search_by_vector(vector, top_k, score_threshold)

    async def search_by_vector(
        self,
        vector: list[float],
        top_k: int = 20,
        score_threshold: float | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Return nearest events for a pre-computed vector."""
        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=top_k,
            score_threshold=score_threshold,
        )

        return [(str(hit.id), hit.score, hit.payload or {}) for hit in results.points]

    def count(self) -> int:
        """Return the number of vectors in the collection."""
        info = self.client.get_collection(COLLECTION_NAME)
        return info.points_count or 0
