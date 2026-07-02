"""Outbox worker — background asyncio task that polls outbox and executes PSP calls."""

import asyncio
import logging

logger = logging.getLogger(__name__)


class OutboxWorker:
    """Background task that polls the outbox table and executes pending PSP calls."""

    def __init__(self, poll_interval: float = 1.0, batch_size: int = 100):
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._running = False

    async def start(self) -> None:
        """Start the outbox polling loop (runs forever)."""
        self._running = True
        logger.info(
            "Outbox worker started (interval=%ss, batch=%d)",
            self._poll_interval,
            self._batch_size,
        )
        while self._running:
            try:
                # Stub — will poll outbox and execute PSP calls.
                pass
            except Exception:
                logger.exception("Outbox worker cycle failed")
            await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        """Signal the worker to shut down."""
        self._running = False
