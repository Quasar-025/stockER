"""Redpanda (Kafka) producer and consumer for event streaming."""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from confluent_kafka import Consumer, KafkaError, Producer

from app.config import settings

logger = logging.getLogger(__name__)


def get_kafka_config() -> dict[str, str]:
    """Base Kafka config for Redpanda."""
    return {
        "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
    }


class EventProducer:
    """Produces events to Redpanda topics."""

    def __init__(self) -> None:
        """Initialize the Kafka producer."""
        self.producer = Producer(get_kafka_config())

    def _delivery_report(self, err: Any, msg: Any) -> None:
        """Callback triggered on successful or failed message delivery."""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")

    def produce(self, topic: str, key: str, value: dict[str, Any]) -> None:
        """Produce a JSON message to a topic."""
        try:
            self.producer.produce(
                topic,
                key=key.encode("utf-8"),
                value=json.dumps(value).encode("utf-8"),
                callback=self._delivery_report,
            )
            # Poll to handle delivery reports
            self.producer.poll(0)
        except Exception as e:
            logger.error(f"Failed to produce message to {topic}: {e}")

    def flush(self, timeout: float = 10.0) -> None:
        """Wait for all messages to be delivered."""
        self.producer.flush(timeout)


class EventConsumer:
    """Consumes events from Redpanda topics."""

    def __init__(self, group_id: str, topics: list[str]) -> None:
        """Initialize the Kafka consumer."""
        config = get_kafka_config()
        config.update(
            {"group.id": group_id, "auto.offset.reset": "earliest", "enable.auto.commit": False}  # type: ignore[dict-item]
        )
        self.consumer = Consumer(config)
        self.consumer.subscribe(topics)
        self._running = False

    async def consume(self, callback: Callable[[str, str, dict[str, Any]], None]) -> None:
        """Continuously consume messages and process them via callback."""
        self._running = True
        logger.info(f"Started consuming topics: {self.consumer.assignment()}")

        try:
            while self._running:
                # Use a short timeout so we don't block the asyncio event loop completely
                msg = self.consumer.poll(0.1)

                if msg is None:
                    await asyncio.sleep(0.01)
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(f"End of partition reached {msg.topic()}/{msg.partition()}")
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                    continue

                # Process the message
                topic = msg.topic()
                key = msg.key().decode("utf-8") if msg.key() else ""

                try:
                    value = json.loads(msg.value().decode("utf-8"))

                    # Execute callback (handle both sync and async)
                    if asyncio.iscoroutinefunction(callback):
                        await callback(topic, key, value)
                    else:
                        callback(topic, key, value)

                    # Commit offset only after successful processing
                    self.consumer.commit(asynchronous=True)

                except json.JSONDecodeError:
                    logger.error(f"Failed to parse message from {topic}: {msg.value()}")
                except Exception as e:
                    logger.error(f"Error processing message from {topic}: {e}")

        finally:
            self.consumer.close()

    def stop(self) -> None:
        """Stop consuming messages."""
        self._running = False
