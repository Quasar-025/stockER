"""Tests for the Event Streaming module (Redpanda/Kafka)."""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

from app.streaming.events import EventProducer, EventConsumer


def test_producer_produce():
    """Test that the producer correctly formats and sends messages."""
    with patch("app.streaming.events.Producer") as mock_producer_class:
        mock_producer_instance = MagicMock()
        mock_producer_class.return_value = mock_producer_instance
        
        producer = EventProducer()
        
        producer.produce(
            topic="test_topic",
            key="test_key",
            value={"message": "hello"}
        )
        
        mock_producer_instance.produce.assert_called_once_with(
            "test_topic",
            key=b"test_key",
            value=b'{"message": "hello"}',
            callback=producer._delivery_report
        )
        mock_producer_instance.poll.assert_called_once_with(0)


@pytest.mark.asyncio
async def test_consumer_consume():
    """Test that the consumer correctly reads and processes messages."""
    with patch("app.streaming.events.Consumer") as mock_consumer_class:
        mock_consumer_instance = MagicMock()
        mock_consumer_class.return_value = mock_consumer_instance
        
        # Mock message
        mock_msg = MagicMock()
        mock_msg.error.return_value = None
        mock_msg.topic.return_value = "test_topic"
        mock_msg.key.return_value = b"test_key"
        mock_msg.value.return_value = b'{"message": "hello"}'
        
        # Setup poll to return the message once, then return None to allow processing, 
        # and we'll break the loop in the callback
        mock_consumer_instance.poll.side_effect = [mock_msg, None, None]
        
        consumer = EventConsumer(group_id="test_group", topics=["test_topic"])
        
        # We need the callback to stop the consumer to avoid infinite loop
        async def mock_callback(topic, key, value):
            assert topic == "test_topic"
            assert key == "test_key"
            assert value == {"message": "hello"}
            consumer.stop()
            
        await consumer.consume(mock_callback)
        
        mock_consumer_instance.commit.assert_called_once_with(asynchronous=True)
        mock_consumer_instance.close.assert_called_once()
