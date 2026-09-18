"""Finnhub WebSocket client for real-time price streaming."""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import websockets

from app.config import settings

logger = logging.getLogger(__name__)


class FinnhubWebSocketClient:
    """Client for receiving real-time trades from Finnhub via WebSocket."""

    BASE_WS_URL = "wss://ws.finnhub.io"

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the WebSocket client."""
        self.api_key = api_key or settings.FINNHUB_API_KEY
        if not self.api_key:
            raise ValueError("Finnhub API key is required")

        self.ws_url = f"{self.BASE_WS_URL}?token={self.api_key}"
        self.connection = None
        self.callbacks: list[Callable[[dict[str, Any]], None]] = []
        self.subscribed_tickers: set[str] = set()
        self._running = False

    def add_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Add a callback function to handle incoming trade data."""
        self.callbacks.append(callback)

    async def connect(self) -> None:
        """Establish the WebSocket connection and start listening."""
        self._running = True

        while self._running:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    self.connection = websocket
                    logger.info("Connected to Finnhub WebSocket")

                    # Re-subscribe to any previously subscribed tickers after reconnect
                    for ticker in self.subscribed_tickers:
                        await self._send_subscribe(ticker)

                    await self._listen()

            except websockets.exceptions.ConnectionClosed:
                logger.warning("Finnhub WebSocket connection closed. Reconnecting in 5s...")
                self.connection = None
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Finnhub WebSocket error: {e}. Reconnecting in 5s...")
                self.connection = None
                await asyncio.sleep(5)

    async def _listen(self) -> None:
        """Listen for incoming messages."""
        if not self.connection:
            return

        async for message in self.connection:
            if not self._running:
                break

            try:
                data = json.loads(message)

                # 'data' type means trade events
                if data.get("type") == "data":
                    for callback in self.callbacks:
                        # Depending on the callback, it might be an async function.
                        # For simplicity, we assume synchronous or we could create tasks.
                        if asyncio.iscoroutinefunction(callback):
                            task = asyncio.create_task(callback(data))
                            self._tasks.add(task)
                            task.add_done_callback(self._tasks.discard)
                        else:
                            callback(data)
                elif data.get("type") == "ping":
                    pass  # Keepalive
                else:
                    logger.debug(f"Received non-trade message: {data}")

            except json.JSONDecodeError:
                logger.error(f"Failed to parse Finnhub WebSocket message: {message}")

    async def _send_subscribe(self, ticker: str) -> None:
        """Send a subscribe message to the WebSocket."""
        if self.connection:
            await self.connection.send(json.dumps({"type": "subscribe", "symbol": ticker}))

    async def subscribe(self, ticker: str) -> None:
        """Subscribe to real-time trades for a ticker."""
        self.subscribed_tickers.add(ticker)
        await self._send_subscribe(ticker)
        logger.info(f"Subscribed to trades for {ticker}")

    async def unsubscribe(self, ticker: str) -> None:
        """Unsubscribe from real-time trades for a ticker."""
        if ticker in self.subscribed_tickers:
            self.subscribed_tickers.remove(ticker)
            if self.connection:
                await self.connection.send(json.dumps({"type": "unsubscribe", "symbol": ticker}))
            logger.info(f"Unsubscribed from trades for {ticker}")

    async def close(self) -> None:
        """Close the WebSocket connection."""
        self._running = False
        if self.connection:
            await self.connection.close()
            self.connection = None
        logger.info("Finnhub WebSocket closed")
