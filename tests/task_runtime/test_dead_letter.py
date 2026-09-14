"""Tests for the RabbitMQ dead-letter publisher adapter."""

from unittest.mock import MagicMock, patch

from celery import Celery

from app.task_runtime.dead_letter import CeleryDeadLetterPublisher, DeadLetterMessage


def test_celery_dead_letter_publisher_targets_durable_dlq() -> None:
    """Publish enriched terminal evidence to the isolated critical DLQ."""
    celery = MagicMock(spec=Celery)
    message = DeadLetterMessage(
        task_id="task-1",
        task_name="refund.process_payment",
        tenant_id="tenant-a",
        idempotency_key="idem-1",
        correlation_id="corr-1",
        attempt=4,
        failure_code="RETRY_EXHAUSTED",
        failure_reason="provider unavailable",
        envelope={"schema_version": 1},
    )

    connection = MagicMock()
    producer = connection.__enter__.return_value.Producer.return_value
    with patch("app.task_runtime.dead_letter.Connection", return_value=connection) as factory:
        result = CeleryDeadLetterPublisher(
            celery, broker_url="amqp://guest:guest@rabbitmq//"
        ).publish(message)

    assert result == "task-1"
    factory.assert_called_once_with("amqp://guest:guest@rabbitmq//", connect_timeout=2)
    producer.publish.assert_called_once()
    call = producer.publish.call_args
    assert call.args == (message.model_dump(mode="json"),)
    assert call.kwargs["routing_key"] == "critical.dead"
    assert call.kwargs["delivery_mode"] == 2
    assert call.kwargs["retry"] is True
