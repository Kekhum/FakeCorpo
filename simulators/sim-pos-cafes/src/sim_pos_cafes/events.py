import logging

from aiokafka import AIOKafkaProducer

from fakecorpo_shared.schemas.pos import TransactionCompleted

log = logging.getLogger(__name__)


class EventPublisher:
    def __init__(self, producer: AIOKafkaProducer, topic_transaction: str) -> None:
        self._producer = producer
        self._topic_transaction = topic_transaction

    async def publish_transaction(self, event: TransactionCompleted) -> None:
        await self._producer.send_and_wait(
            self._topic_transaction,
            value=event.model_dump_json().encode("utf-8"),
            key=event.cafe_code.encode("utf-8"),
        )
