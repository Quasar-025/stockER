"""Tests for the FRED client."""

import pytest
import httpx
from unittest.mock import patch, AsyncMock

from app.ingestion.fred import FREDClient


@pytest.fixture
def mock_fred_api_key(monkeypatch):
    """Mock the API key setting."""
    monkeypatch.setenv("FRED_API_KEY", "test_api_key")


@pytest.mark.asyncio
async def test_fred_client_requires_api_key(monkeypatch):
    """Test that missing API key raises ValueError."""
    monkeypatch.setattr("app.config.settings.FRED_API_KEY", "")
    
    with pytest.raises(ValueError, match="FRED API key is required"):
        FREDClient()


@pytest.mark.asyncio
async def test_get_series_observations():
    """Test fetching economic data points."""
    client = FREDClient(api_key="test_api_key")
    
    mock_response = httpx.Response(200, json={
        "realtime_start": "2024-01-01",
        "realtime_end": "2024-01-01",
        "observation_start": "1600-01-01",
        "observation_end": "9999-12-31",
        "units": "lin",
        "output_type": 1,
        "file_type": "json",
        "order_by": "observation_date",
        "sort_order": "desc",
        "count": 1,
        "offset": 0,
        "limit": 100,
        "observations": [
            {
                "realtime_start": "2024-01-01",
                "realtime_end": "2024-01-01",
                "date": "2023-12-01",
                "value": "3.7"
            }
        ]
    })
    
    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        with patch("app.ingestion.fred.rate_limiter.acquire", new_callable=AsyncMock):
            observations = await client.get_series_observations("UNRATE", limit=1)
            
            assert len(observations) == 1
            assert observations[0]["date"] == "2023-12-01"
            assert observations[0]["value"] == "3.7"

    await client.close()
