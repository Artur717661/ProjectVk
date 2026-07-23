import json
import uuid
from datetime import UTC, datetime

import structlog
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from app.core.config import get_settings
from app.core.errors import KafkaUnavailableError
from app.core.metrics import kafka_publish_errors_total

logger = structlog.get_logger(__name__)


class KafkaProducerClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._topic = settings.kafka_topic
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        self._started = False

    @property
    def is_started(self) -> bool:
        return self._started

    async def start(self) -> None:
        if not self._started:
            await self._producer.start()
            self._started = True
            logger.info("kafka_producer_started")

    async def stop(self) -> None:
        if self._started:
            await self._producer.stop()
            self._started = False
            logger.info("kafka_producer_stopped")

    async def publish_analysis_requested(
        self, *, photo_id: uuid.UUID, object_key: str, trace_id: str
    ) -> None:
        message = {
            "photo_id": str(photo_id),
            "object_key": object_key,
            "created_at": datetime.now(UTC).isoformat(),
            "trace_id": trace_id,
        }
        try:
            await self._producer.send_and_wait(self._topic, value=message)
        except KafkaError as exc:
            kafka_publish_errors_total.inc()
            logger.error("kafka_publish_failed", photo_id=str(photo_id), error=str(exc))
            raise KafkaUnavailableError(f"Failed to publish to Kafka: {exc}") from exc


_producer_client: KafkaProducerClient | None = None


def get_kafka_producer() -> KafkaProducerClient:
    global _producer_client
    if _producer_client is None:
        _producer_client = KafkaProducerClient()
    return _producer_client
