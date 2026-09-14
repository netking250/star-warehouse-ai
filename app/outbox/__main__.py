"""Run the independently deployable transactional outbox relay."""

from __future__ import annotations

import asyncio
import signal
from types import FrameType

from app.celery_app import celery_app
from app.core.config import settings
from app.outbox.publisher import CeleryTaskPublisher
from app.outbox.relay import OutboxRelay


async def _run() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop(_signum: int | None = None, _frame: FrameType | None = None) -> None:
        loop.call_soon_threadsafe(stop_event.set)

    for stop_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(stop_signal, request_stop)
        except NotImplementedError:
            signal.signal(stop_signal, request_stop)

    relay = OutboxRelay(
        publisher=CeleryTaskPublisher(celery_app),
        batch_size=settings.OUTBOX_BATCH_SIZE,
        poll_interval_seconds=settings.OUTBOX_POLL_INTERVAL_SECONDS,
        lease_seconds=settings.OUTBOX_LEASE_SECONDS,
        retry_base_seconds=settings.OUTBOX_RETRY_BASE_SECONDS,
        retry_max_seconds=settings.OUTBOX_RETRY_MAX_SECONDS,
    )
    await relay.run_forever(stop_event)


def main() -> None:
    """Run the relay until SIGINT or SIGTERM requests graceful shutdown."""
    asyncio.run(_run())


if __name__ == "__main__":
    main()
