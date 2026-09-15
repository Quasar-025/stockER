"""Tests for the FRED client."""

import pytest
import httpx
from unittest.mock import patch, AsyncMock

from app.ingestion.fred import FREDClient


def _mock_response(status_code: int = 200, json_data=None) -> httpx.Response:
    request = httpx.Request("GET", "https://test.example.com")
    return httpx.Response(status_code, json=json_data, request=request)


@pytest.mark.asyncio
async def test_fred_client_requires_api_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.FRED_API_KEY", "")
    with pytest.raises(ValueError, match="FRED API key is required"):
        FREDClient()


@pytest.mark.asyncio
async def test_get_series_observations():
    client = FREDClient(api_key="test_api_key")

    mock_resp = _mock_response(json_data={
        "observations": [
            {"date": "2023-12-01", "value": "3.7"}
        ]
    })

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        with patch("app.ingestion.fred.rate_limiter.acquire", new_callable=AsyncMock):
            observations = await client.get_series_observations("UNRATE", limit=1)
            assert len(observations) == 1
            assert observations[0]["date"] == "2023-12-01"
            assert observations[0]["value"] == "3.7"

    await client.close()
