"""Text embedding via Ollama (local, free) with OpenAI fallback.

Uses ``nomic-embed-text`` by default, which produces 768-dimension vectors
well-suited for financial news semantic search.
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate text embeddings from a local Ollama model or OpenAI fallback."""

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider or settings.EMBEDDING_PROVIDER
        self.model = model or settings.EMBEDDING_MODEL
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        """Expected vector dimensionality for the configured model."""
        if self._dimension is not None:
            return self._dimension
        # nomic-embed-text → 768; text-embedding-3-small → 1536
        model_dims: dict[str, int] = {
            "nomic-embed-text": 768,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return model_dims.get(self.model, 768)

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string and return its vector."""
        if self.provider == "ollama":
            return await self._embed_ollama(text)
        elif self.provider == "openai":
            return await self._embed_openai(text)
        else:
            raise ValueError(f"Unknown embedding provider: {self.provider}")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts.  Falls back to sequential for Ollama."""
        if self.provider == "openai":
            return await self._embed_openai_batch(texts)

        # Ollama: sequential embedding (no native batch in the embed endpoint)
        results: list[list[float]] = []
        for text in texts:
            vec = await self._embed_ollama(text)
            results.append(vec)
        return results

    async def _embed_ollama(self, text: str) -> list[float]:
        """Generate embedding via local Ollama."""
        try:
            import ollama

            client = ollama.AsyncClient(host=settings.OLLAMA_HOST)
            response = await client.embed(model=self.model, input=text)
            embeddings = response.get("embeddings", [])
            if embeddings:
                vector = embeddings[0]
                self._dimension = len(vector)
                return vector
            raise ValueError("Ollama returned empty embeddings")
        except Exception as e:
            logger.error(f"Ollama embedding failed: {e}")
            raise

    async def _embed_openai(self, text: str) -> list[float]:
        """Generate embedding via OpenAI API."""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.embeddings.create(
                model=self.model,
                input=text,
            )
            vector = response.data[0].embedding
            self._dimension = len(vector)
            return vector
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise

    async def _embed_openai_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embedding via OpenAI (supports native batching)."""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.embeddings.create(
                model=self.model,
                input=texts,
            )
            vectors = [item.embedding for item in response.data]
            if vectors:
                self._dimension = len(vectors[0])
            return vectors
        except Exception as e:
            logger.error(f"OpenAI batch embedding failed: {e}")
            raise
