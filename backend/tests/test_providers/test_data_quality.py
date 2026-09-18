from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.providers import FinnhubProvider
from app.providers.data_quality import DataQualityRecord, DataStatus


def test_missing_source_timestamp_is_explicitly_delayed() -> None:
    quality = DataQualityRecord.from_source(source="test", source_timestamp=None)

    assert quality.status == DataStatus.DELAYED
    assert quality.freshness_seconds is None
    assert quality.data_quality < 1.0


def test_old_source_timestamp_is_stale() -> None:
    quality = DataQualityRecord.from_source(
        source="test",
        source_timestamp=datetime.now(UTC) - timedelta(days=2),
        stale_after_seconds=3600,
    )

    assert quality.status == DataStatus.STALE
    assert quality.freshness_seconds is not None


@pytest.mark.asyncio
async def test_finnhub_adapter_preserves_data_and_attaches_quality() -> None:
    client = AsyncMock()
    client.get_company_news.return_value = [{"headline": "Test"}]
    provider = FinnhubProvider(client=client)

    payload = await provider.company_news("TSM", "2024-01-01", "2024-01-02")

    assert payload.data == [{"headline": "Test"}]
    assert payload.quality.source == "finnhub"
    assert payload.quality.status == DataStatus.DELAYED
    client.get_company_news.assert_awaited_once()
