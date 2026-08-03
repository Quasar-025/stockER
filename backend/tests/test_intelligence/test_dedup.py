"""Tests for the deduplication engine."""

from app.intelligence.dedup import DeduplicationEngine, DeduplicationResult


class TestDeduplicationEngine:
    """Tests for the multi-layer dedup engine."""

    def test_first_article_not_duplicate(self):
        engine = DeduplicationEngine()
        result = engine.check(
            url="https://example.com/article1",
            title="Fed raises rates",
            description="The Federal Reserve raised rates today.",
        )
        assert result.is_duplicate is False
        assert engine.cache_size == 1

    def test_exact_url_duplicate(self):
        engine = DeduplicationEngine()
        engine.check("https://example.com/a1", "Title", "Description")
        result = engine.check("https://example.com/a1", "Different Title", "Different Desc")
        assert result.is_duplicate is True
        assert result.similarity_score == 1.0
        assert result.duplicate_of == "https://example.com/a1"

    def test_title_fingerprint_duplicate(self):
        engine = DeduplicationEngine()
        engine.check("https://a.com/1", "Fed raises rates by 25 bps", "Desc 1")
        # Same title from different source
        result = engine.check("https://b.com/2", "Fed raises rates by 25 bps", "Desc 2")
        assert result.is_duplicate is True
        assert result.similarity_score == 0.95

    def test_title_normalization(self):
        """Test that common prefixes are stripped."""
        engine = DeduplicationEngine()
        engine.check("https://a.com/1", "Fed raises rates", "Desc")
        # 'Breaking:' prefix should be stripped
        result = engine.check("https://b.com/2", "Breaking: Fed raises rates", "Different")
        assert result.is_duplicate is True

    def test_content_hash_duplicate(self):
        engine = DeduplicationEngine()
        desc = "The Federal Reserve raised interest rates by 25 basis points."
        engine.check("https://a.com/1", "Title A", desc)
        # Same content, different title and URL
        result = engine.check("https://b.com/2", "Title B", desc)
        assert result.is_duplicate is True
        assert result.similarity_score == 0.99

    def test_different_articles_not_duplicate(self):
        engine = DeduplicationEngine()
        engine.check("https://a.com/1", "Fed raises rates", "The Fed raised rates.")
        result = engine.check("https://b.com/2", "Apple earnings beat", "Apple reported Q4.")
        assert result.is_duplicate is False
        assert engine.cache_size == 2

    def test_cache_size_tracking(self):
        engine = DeduplicationEngine()
        for i in range(5):
            engine.check(f"https://example.com/{i}", f"Title {i}", f"Desc {i}")
        assert engine.cache_size == 5
