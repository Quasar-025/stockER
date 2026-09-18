"""Tests for the Market Microstructure client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.ingestion.microstructure import MicrostructureClient


def _mock_response(status_code: int = 200, json_data=None) -> httpx.Response:
    request = httpx.Request("GET", "https://test.example.com")
    return httpx.Response(status_code, json=json_data, request=request)


@pytest.mark.asyncio
async def test_get_basic_financials():
    client = MicrostructureClient(api_key="test_api_key")

    mock_resp = _mock_response(json_data={
        "metric": {
            "beta": 1.2,
            "shortInterest": 15000000,
            "shortRatio": 2.5,
            "52WeekHigh": 200.0,
            "52WeekLow": 120.0,
            "10DayAverageTradingVolume": 50000000,
        }
    })

    with patch.object(client.client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        with patch("app.ingestion.microstructure.rate_limiter.acquire", new_callable=AsyncMock):
            data = await client.get_basic_financials("AAPL")
            assert data["ticker"] == "AAPL"
            assert data["beta"] == 1.2
            assert data["short_interest"] == 15000000

    await client.close()
