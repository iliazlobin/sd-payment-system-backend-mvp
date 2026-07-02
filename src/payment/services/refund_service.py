"""Refund service — outbox dispatch for refund."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payment.models.outbox import Outbox
from payment.models.payment_intent import PaymentIntent


class RefundService:
    """Handles refund of captured payment intents."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def refund(self, intent_id: uuid.UUID, amount: int | None = None) -> dict:
        """Initiate refund for a captured payment intent.

        If amount is None, refunds the full intent amount.

        Raises LookupError if intent not found.
        Raises ValueError if intent is not in 'captured' status.
        Raises ValueError if refund amount exceeds intent amount.
        """
        result = await self._db.execute(
            select(PaymentIntent).where(PaymentIntent.id == intent_id)
        )
        intent = result.scalar_one_or_none()
        if intent is None:
            raise LookupError(f"Payment intent {intent_id} not found")

        if intent.status != "captured":
            raise ValueError(f"Cannot refund intent in status '{intent.status}'")

        refund_amount = amount if amount is not None else intent.amount

        if refund_amount > intent.amount:
            raise ValueError(
                f"Refund amount {refund_amount} exceeds intent amount "
                f"{intent.amount}"
            )

        # Write outbox row — durable dispatch
        outbox_row = Outbox(
            id=uuid.uuid4(),
            event_type="refund_requested",
            payload={
                "intent_id": str(intent_id),
                "amount": refund_amount,
                "psp_reference": intent.psp_reference,
            },
            retry_count=0,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(outbox_row)

        # Transition to refunding
        intent.status = "refunding"
        await self._db.commit()

        return {
            "id": str(intent.id),
            "status": intent.status,
            "refund_amount": refund_amount,
        }
