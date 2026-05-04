import logging

from aiokafka import AIOKafkaProducer

from fakecorpo_shared.schemas.procurement import (
    PurchaseOrderArrived,
    PurchaseOrderCreated,
)

log = logging.getLogger(__name__)


class EventPublisher:
    def __init__(
        self,
        producer: AIOKafkaProducer,
        topic_po_created: str,
        topic_po_arrived: str,
    ) -> None:
        self._producer = producer
        self._topic_po_created = topic_po_created
        self._topic_po_arrived = topic_po_arrived

    async def publish_po_created(self, event: PurchaseOrderCreated) -> None:
        await self._producer.send_and_wait(
            self._topic_po_created,
            value=event.model_dump_json().encode("utf-8"),
            key=str(event.po_id).encode("utf-8"),
        )
        log.info(
            "event.po_created po_id=%d po_number=%s supplier=%s contract=%.2f %s invoice=%.2f %s",
            event.po_id, event.po_number, event.supplier_code,
            event.total_amount, event.currency,
            event.invoice_amount, event.invoice_currency,
        )

    async def publish_po_arrived(self, event: PurchaseOrderArrived) -> None:
        await self._producer.send_and_wait(
            self._topic_po_arrived,
            value=event.model_dump_json().encode("utf-8"),
            key=str(event.po_id).encode("utf-8"),
        )
        log.info(
            "event.po_arrived po_id=%d po_number=%s status=%s delay=%+dd quality=%s accepted_kg=%.1f",
            event.po_id, event.po_number, event.arrival_status,
            event.delay_days, event.quality_status,
            event.quantity_accepted_kg,
        )
