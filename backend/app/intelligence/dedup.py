"""Article-to-Event deduplication engine.

Prevents the same event from being classified and stored multiple
times when covered by multiple news sources. Uses a combination of
URL dedup (exact) and semantic similarity dedup (fuzzy).
"""

import hashlib
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DeduplicationResult:
    """Result of a deduplication check."""

    is_duplicate: bool
    duplicate_of: str | None = None  # URL of the original
    similarity_score: float = 0.0


class DeduplicationEngine:
    """Multi-layer deduplication for incoming news articles.

    Layer 1: Exact URL match (O(1) lookup)
    Layer 2: Title fingerprint (normalized, lowercased, stripped)
    Layer 3: Content hash (SHA-256 of description text)

    Note: Semantic similarity dedup (via Qdrant) will be added in the
    similarity engine phase — this handles the deterministic layers.
    """

    def __init__(self, ttl_hours: int = 72) -> None:
        """Initialize with a TTL for the in-memory cache."""
        self.ttl = timedelta(hours=ttl_hours)
        self._url_cache: dict[str, datetime] = {}
        self._title_cache: dict[str, str] = {}  # fingerprint -> original URL
        self._content_cache: dict[str, str] = {}  # hash -> original URL

    def _normalize_title(self, title: str) -> str:
        """Normalize a title for fingerprinting."""
        # Lowercase, strip whitespace, remove common prefixes
        normalized = title.lower().strip()
        # Remove common noise prefixes
        for prefix in ["breaking:", "update:", "exclusive:", "report:"]:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        return normalized

    def _content_hash(self, text: str) -> str:
        """Create a SHA-256 hash of content text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _evict_expired(self) -> None:
        """Remove entries older than TTL."""
        now = datetime.utcnow()
        expired_urls = [
            url for url, ts in self._url_cache.items()
            if now - ts > self.ttl
        ]
        for url in expired_urls:
            del self._url_cache[url]
            # Also remove from reverse caches
            self._title_cache = {
                k: v for k, v in self._title_cache.items() if v != url
            }
            self._content_cache = {
                k: v for k, v in self._content_cache.items() if v != url
            }

    def check(self, url: str, title: str, description: str) -> DeduplicationResult:
        """Check if an article is a duplicate.

        Returns a DeduplicationResult indicating whether the article
        should be skipped or processed.
        """
        self._evict_expired()

        # Layer 1: Exact URL match
        if url in self._url_cache:
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_of=url,
                similarity_score=1.0,
            )

        # Layer 2: Title fingerprint
        title_fp = self._normalize_title(title)
        if title_fp in self._title_cache:
            original_url = self._title_cache[title_fp]
            logger.debug(f"Title dedup: '{title}' matches '{original_url}'")
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_of=original_url,
                similarity_score=0.95,
            )

        # Layer 3: Content hash
        content_hash = self._content_hash(description)
        if content_hash in self._content_cache:
            original_url = self._content_cache[content_hash]
            logger.debug(f"Content dedup: hash matches '{original_url}'")
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_of=original_url,
                similarity_score=0.99,
            )

        # Not a duplicate — register it
        now = datetime.utcnow()
        self._url_cache[url] = now
        self._title_cache[title_fp] = url
        self._content_cache[content_hash] = url

        return DeduplicationResult(is_duplicate=False)

    @property
    def cache_size(self) -> int:
        """Number of articles currently in the dedup cache."""
        return len(self._url_cache)
