"""Capture service — outbox dispatch for capture."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payment.models.outbox import Outbox
from payment.models.payment_intent import PaymentIntent


class CaptureService:
    """Handles capture of authorized payment intents via outbox."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def capture(self, intent_id: uuid.UUID) -> dict:
        """Initiate capture for a payment intent.

        Raises LookupError if intent not found.
        Raises ValueError if intent is not in 'authorized' status.
        """
        result = await self._db.execute(
            select(PaymentIntent).where(PaymentIntent.id == intent_id)
        )
        intent = result.scalar_one_or_none()
        if intent is None:
            raise LookupError(f"Payment intent {intent_id} not found")

        if intent.status != "authorized":
            raise ValueError(f"Cannot capture intent in status '{intent.status}'")

        # Transition to capturing
        intent.status = "capturing"

        # Write outbox row — durable dispatch
        outbox_row = Outbox(
            id=uuid.uuid4(),
            event_type="capture_requested",
            payload={
                "intent_id": str(intent_id),
                "amount": intent.amount,
                "psp_reference": intent.psp_reference,
            },
            retry_count=0,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(outbox_row)
        await self._db.commit()

        return {
            "id": str(intent.id),
            "status": intent.status,
            "amount": intent.amount,
            "currency": intent.currency,
            "psp_reference": intent.psp_reference,
        }
