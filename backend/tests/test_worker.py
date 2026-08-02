"""Tests for Celery worker tasks."""

import pytest
from unittest.mock import patch, AsyncMock

from app.tasks import fetch_latest_sec_filings, fetch_macro_indicators


@patch("app.tasks.SecEdgarClient")
@patch("app.tasks.EventProducer")
def test_fetch_latest_sec_filings_task(mock_producer_class, mock_sec_client_class):
    """Test the Celery task that fetches SEC filings and streams them."""
    # Setup mocks
    mock_sec_client = mock_sec_client_class.return_value
    mock_producer = mock_producer_class.return_value
    
    # We have to mock the async method get_latest_filings
    mock_sec_client.get_latest_filings = AsyncMock(return_value=[
        {"title": "8-K", "updated": "2024-01-01T12:00:00Z", "link": "http", "summary": "test"}
    ])
    mock_sec_client.close = AsyncMock()
    
    # Run the task synchronously (Celery testing pattern or just call it directly)
    # Since fetch_latest_sec_filings handles its own asyncio loop, we can just call it
    result = fetch_latest_sec_filings("AAPL")
    
    assert result == {"status": "success", "count": 1}
    mock_sec_client.get_latest_filings.assert_called_once_with("AAPL")
    mock_producer.produce.assert_called_once()
    mock_producer.flush.assert_called_once()


@patch("app.tasks.FREDClient")
@patch("app.tasks.EventProducer")
def test_fetch_macro_indicators_task(mock_producer_class, mock_fred_client_class):
    """Test the Celery task that fetches macroeconomic data."""
    # Setup mocks
    mock_fred_client = mock_fred_client_class.return_value
    mock_producer = mock_producer_class.return_value
    
    mock_fred_client.get_series_observations = AsyncMock(return_value=[
        {"date": "2024-01-01", "value": "1.0"}
    ])
    mock_fred_client.close = AsyncMock()
    
    result = fetch_macro_indicators()
    
    assert result["status"] == "success"
    # Should fetch CPIAUCSL, FEDFUNDS, UNRATE
    assert mock_fred_client.get_series_observations.call_count == 3
    assert mock_producer.produce.call_count == 3
    mock_producer.flush.assert_called_once()
