import logging

from aiokafka import AIOKafkaProducer

from fakecorpo_shared.schemas.production import (
    BatchCompleted,
    BatchStarted,
    RoasterTelemetry,
)

log = logging.getLogger(__name__)


class EventPublisher:
    def __init__(
        self,
        producer: AIOKafkaProducer,
        topic_batch_started: str,
        topic_batch_completed: str,
        topic_telemetry: str,
    ) -> None:
        self._producer = producer
        self._topic_batch_started = topic_batch_started
        self._topic_batch_completed = topic_batch_completed
        self._topic_telemetry = topic_telemetry

    async def publish_batch_started(self, event: BatchStarted) -> None:
        await self._producer.send_and_wait(
            self._topic_batch_started,
            value=event.model_dump_json().encode("utf-8"),
            key=str(event.batch_id).encode("utf-8"),
        )
        log.info(
            "event.batch_started batch_id=%d batch=%s sku=%s brand=%s input_kg=%.1f",
            event.batch_id, event.batch_number, event.sku_code, event.brand,
            event.planned_input_kg,
        )

    async def publish_batch_completed(self, event: BatchCompleted) -> None:
        await self._producer.send_and_wait(
            self._topic_batch_completed,
            value=event.model_dump_json().encode("utf-8"),
            key=str(event.batch_id).encode("utf-8"),
        )
        log.info(
            "event.batch_completed batch_id=%d sku=%s status=%s output_kg=%.1f loss=%.1f%% cupping=%.1f",
            event.batch_id, event.sku_code, event.status,
            event.output_kg, event.weight_loss_pct * 100, event.cupping_score,
        )

    async def publish_telemetry(self, event: RoasterTelemetry) -> None:
        await self._producer.send_and_wait(
            self._topic_telemetry,
            value=event.model_dump_json().encode("utf-8"),
            key=str(event.batch_id).encode("utf-8"),
        )
