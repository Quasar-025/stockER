"""Tests for the rate limiter utility."""

import time

import pytest

from app.utils.rate_limiter import RateLimitConfig, RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_no_config():
    """Test that an unregistered API name passes through without blocking."""
    limiter = RateLimiter()
    # Should return immediately without errors
    await limiter.acquire("unknown_api")


@pytest.mark.asyncio
async def test_rate_limiter_tracks_calls():
    """Test that calls are tracked per API."""
    limiter = RateLimiter()
    limiter.register("test_api", RateLimitConfig(calls_per_minute=100))

    await limiter.acquire("test_api")
    await limiter.acquire("test_api")

    assert len(limiter._minute_calls["test_api"]) == 2


@pytest.mark.asyncio
async def test_rate_limiter_daily_limit_exceeded():
    """Test that exceeding daily limit raises RuntimeError."""
    limiter = RateLimiter()
    limiter.register("limited_api", RateLimitConfig(calls_per_minute=100, calls_per_day=2))

    await limiter.acquire("limited_api")
    await limiter.acquire("limited_api")

    with pytest.raises(RuntimeError, match="Daily rate limit exceeded"):
        await limiter.acquire("limited_api")


@pytest.mark.asyncio
async def test_rate_limiter_cleans_old_entries():
    """Test that minute-old entries are cleaned."""
    limiter = RateLimiter()
    limiter.register("test_api", RateLimitConfig(calls_per_minute=10))

    # Manually insert an old timestamp (2 minutes ago)
    old_time = time.time() - 120
    limiter._minute_calls["test_api"] = [old_time]

    await limiter.acquire("test_api")

    # Old entry should have been cleaned, only the new call should remain
    assert len(limiter._minute_calls["test_api"]) == 1
    assert limiter._minute_calls["test_api"][0] > old_time
