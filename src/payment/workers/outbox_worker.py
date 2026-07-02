"""Outbox worker — background asyncio task that polls outbox and executes PSP calls."""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payment.models.outbox import Outbox
from payment.models.payment_intent import PaymentIntent
from payment.services.ledger_service import LedgerService
from payment.services.psp_adapter import MockPspAdapter

logger = logging.getLogger(__name__)


class OutboxWorker:
    """Background task that polls the outbox table and executes pending PSP calls."""

    def __init__(
        self,
        db_session_factory,
        poll_interval: float = 1.0,
        batch_size: int = 100,
        max_retries: int = 10,
    ):
        self._session_factory = db_session_factory
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._running = False
        self._psp = MockPspAdapter()

    async def start(self) -> None:
        """Start the outbox polling loop (runs forever until stopped)."""
        self._running = True
        logger.info(
            "Outbox worker started (interval=%ss, batch=%d)",
            self._poll_interval,
            self._batch_size,
        )
        while self._running:
            try:
                await self._poll()
            except Exception:
                logger.exception("Outbox worker cycle failed")
            await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        """Signal the worker to shut down."""
        self._running = False

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    async def _poll(self) -> None:
        """Poll for pending outbox rows and process them one at a time."""
        for _ in range(self._batch_size):
            processed = await self._poll_one()
            if not processed:
                break  # No more pending rows

    async def _poll_one(self) -> bool:
        """Claim and process a single pending outbox row. Returns True if a row was processed."""
        async with self._session_factory() as db:
            async with db.begin():
                # Select one pending row with lock
                result = await db.execute(
                    select(Outbox)
                    .where(Outbox.processed_at.is_(None))
                    .order_by(Outbox.created_at.asc())
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                row = result.scalar_one_or_none()
                if row is None:
                    return False  # Nothing pending

                await self._process_row(db, row)
                return True

    async def _process_row(self, db: AsyncSession, row: Outbox) -> None:
        """Process a single outbox row (inside an active transaction)."""
        try:
            intent_id = row.payload["intent_id"]
            amount = row.payload["amount"]
            psp_reference = row.payload.get("psp_reference", "")

            if row.event_type == "capture_requested":
                await self._handle_capture(db, intent_id, amount, psp_reference)
            elif row.event_type == "refund_requested":
                await self._handle_refund(db, intent_id, amount, psp_reference)

            row.processed_at = datetime.now(timezone.utc)
            row.error = None

        except Exception as exc:
            row.retry_count += 1
            if row.retry_count >= self._max_retries:
                logger.error(
                    "Outbox row %s exceeded max retries (%d), dead-lettering",
                    row.id,
                    self._max_retries,
                )
                row.processed_at = datetime.now(timezone.utc)
            row.error = str(exc)
            raise

    async def _handle_capture(
        self,
        db: AsyncSession,
        intent_id: str,
        amount: int,
        psp_reference: str,
    ) -> None:
        """Execute mock PSP capture and write settlement ledger batch."""
        await self._psp.capture(psp_reference, amount)

        result = await db.execute(
            select(PaymentIntent).where(PaymentIntent.id == UUID(intent_id))
        )
        intent = result.scalar_one_or_none()
        if intent is None:
            logger.warning("Intent %s not found for capture", intent_id)
            return

        intent.status = "captured"

        ledger_svc = LedgerService(db)
        await ledger_svc.insert_batch(UUID(intent_id), "capture settlement", amount)

    async def _handle_refund(
        self,
        db: AsyncSession,
        intent_id: str,
        amount: int,
        psp_reference: str,
    ) -> None:
        """Execute mock PSP refund and write reversal ledger batch."""
        await self._psp.refund(psp_reference, amount)

        result = await db.execute(
            select(PaymentIntent).where(PaymentIntent.id == UUID(intent_id))
        )
        intent = result.scalar_one_or_none()
        if intent is None:
            logger.warning("Intent %s not found for refund", intent_id)
            return

        intent.status = "refunded"

        ledger_svc = LedgerService(db)
        await ledger_svc.insert_batch(UUID(intent_id), "refund reversal", amount)
