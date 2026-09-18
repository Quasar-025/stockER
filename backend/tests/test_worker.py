"""Tests for Celery worker tasks."""

from unittest.mock import AsyncMock, MagicMock, patch


@patch("app.tasks.EventProducer")
@patch("app.tasks.SecEdgarClient")
def test_fetch_latest_sec_filings_task(mock_sec_client_class, mock_producer_class):
    """Test the Celery task that fetches SEC filings and streams them."""
    from app.tasks import fetch_latest_sec_filings

    # Setup mocks
    mock_sec_client = mock_sec_client_class.return_value
    mock_producer = mock_producer_class.return_value

    mock_sec_client.get_latest_filings = AsyncMock(return_value=[
        {"title": "8-K", "updated": "2024-01-01T12:00:00Z", "link": "http", "summary": "test"}
    ])
    mock_sec_client.close = AsyncMock()

    # Celery tasks with bind=True receive `self` as first arg.
    # When calling the function directly (not via .delay()), we pass a mock self.
    result = fetch_latest_sec_filings(MagicMock(), "AAPL")

    assert result == {"status": "success", "count": 1}
    mock_sec_client.get_latest_filings.assert_called_once_with("AAPL")
    mock_producer.produce.assert_called_once()
    mock_producer.flush.assert_called_once()


@patch("app.tasks.EventProducer")
@patch("app.tasks.FREDClient")
def test_fetch_macro_indicators_task(mock_fred_client_class, mock_producer_class):
    """Test the Celery task that fetches macroeconomic data."""
    from app.tasks import fetch_macro_indicators

    # Setup mocks
    mock_fred_client = mock_fred_client_class.return_value
    mock_producer = mock_producer_class.return_value

    mock_fred_client.get_series_observations = AsyncMock(return_value=[
        {"date": "2024-01-01", "value": "1.0"}
    ])
    mock_fred_client.close = AsyncMock()

    result = fetch_macro_indicators(MagicMock())

    assert result["status"] == "success"
    # Should fetch CPIAUCSL, FEDFUNDS, UNRATE
    assert mock_fred_client.get_series_observations.call_count == 3
    assert mock_producer.produce.call_count == 3
    mock_producer.flush.assert_called_once()
