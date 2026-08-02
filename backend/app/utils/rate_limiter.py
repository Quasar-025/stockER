"""Rate limiter utility for external API calls."""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class RateLimitConfig:
    """Configuration for a rate-limited API."""

    calls_per_minute: int
    calls_per_day: int | None = None


@dataclass
class RateLimiter:
    """Token bucket rate limiter for external API calls.

    Tracks per-API rate limits and blocks when limits are exceeded.
    """

    _configs: dict[str, RateLimitConfig] = field(default_factory=dict)
    _minute_calls: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    _day_calls: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def register(self, api_name: str, config: RateLimitConfig) -> None:
        """Register rate limit configuration for an API."""
        self._configs[api_name] = config

    async def acquire(self, api_name: str) -> None:
        """Acquire permission to make an API call. Blocks if rate limited."""
        if api_name not in self._configs:
            return

        config = self._configs[api_name]
        async with self._lock:
            now = time.time()

            # Clean old entries
            minute_ago = now - 60
            self._minute_calls[api_name] = [
                t for t in self._minute_calls[api_name] if t > minute_ago
            ]

            # Check per-minute limit
            if len(self._minute_calls[api_name]) >= config.calls_per_minute:
                wait_time = 60 - (now - self._minute_calls[api_name][0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)

            # Check per-day limit
            if config.calls_per_day is not None:
                day_ago = now - 86400
                self._day_calls[api_name] = [
                    t for t in self._day_calls[api_name] if t > day_ago
                ]
                if len(self._day_calls[api_name]) >= config.calls_per_day:
                    raise RuntimeError(
                        f"Daily rate limit exceeded for {api_name} "
                        f"({config.calls_per_day} calls/day)"
                    )

            # Record the call
            self._minute_calls[api_name].append(time.time())
            if config.calls_per_day is not None:
                self._day_calls[api_name].append(time.time())


# Global rate limiter instance
rate_limiter = RateLimiter()

# Register known API limits
rate_limiter.register("finnhub", RateLimitConfig(calls_per_minute=60))
rate_limiter.register("alphavantage", RateLimitConfig(calls_per_minute=5, calls_per_day=25))
rate_limiter.register("fred", RateLimitConfig(calls_per_minute=120))
rate_limiter.register("sec_edgar", RateLimitConfig(calls_per_minute=10))
