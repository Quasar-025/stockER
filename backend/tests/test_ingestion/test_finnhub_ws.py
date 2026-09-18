"""Tests for the Finnhub WebSocket client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ingestion.finnhub_ws import FinnhubWebSocketClient


@pytest.fixture
def mock_finnhub_api_key(monkeypatch):
    """Mock the API key setting."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test_api_key")


@pytest.mark.asyncio
async def test_finnhub_ws_client_requires_api_key(monkeypatch):
    """Test that missing API key raises ValueError."""
    monkeypatch.setattr("app.config.settings.FINNHUB_API_KEY", "")

    with pytest.raises(ValueError, match="Finnhub API key is required"):
        FinnhubWebSocketClient()


@pytest.mark.asyncio
async def test_subscribe_and_unsubscribe():
    """Test subscribing and unsubscribing adds/removes from the set."""
    client = FinnhubWebSocketClient(api_key="test_api_key")

    # Mock the connection so we don't actually send network traffic
    client.connection = AsyncMock()

    await client.subscribe("AAPL")
    assert "AAPL" in client.subscribed_tickers
    client.connection.send.assert_called_once()

    await client.unsubscribe("AAPL")
    assert "AAPL" not in client.subscribed_tickers
    assert client.connection.send.call_count == 2

    await client.close()


@pytest.mark.asyncio
async def test_callbacks_executed():
    """Test that registered callbacks are executed when trade data is received."""
    client = FinnhubWebSocketClient(api_key="test_api_key")

    callback_mock = MagicMock()
    client.add_callback(callback_mock)

    # Simulate receiving a message by manually injecting it into the _listen logic
    client.connection = AsyncMock()
    client._running = True

    # We will yield one message then break the loop
    async def mock_async_generator(self=None):
        yield '{"type": "data", "data": [{"s": "AAPL", "p": 150.0, "v": 100}]}'
        client._running = False  # Break the loop on the next iteration

    client.connection.__aiter__ = mock_async_generator

    await client._listen()

    # Ensure the callback was called with the parsed JSON data
    callback_mock.assert_called_once_with({"type": "data", "data": [{"s": "AAPL", "p": 150.0, "v": 100}]})

    await client.close()
