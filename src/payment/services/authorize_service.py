"""Authorize service — mock PSP authorize + ledger batch."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payment.models.payment_intent import PaymentIntent
from payment.services.ledger_service import LedgerService
from payment.services.psp_adapter import MockPspAdapter


class AuthorizeService:
    """Handles authorization of payment intents."""

    def __init__(self, db: AsyncSession, psp_adapter: MockPspAdapter | None = None):
        self._db = db
        self._psp = psp_adapter or MockPspAdapter()

    async def authorize(self, intent_id: uuid.UUID) -> dict:
        """Authorize a payment intent.

        Raises LookupError if intent not found.
        Raises ValueError if intent is not in 'created' status.
        """
        result = await self._db.execute(
            select(PaymentIntent).where(PaymentIntent.id == intent_id)
        )
        intent = result.scalar_one_or_none()
        if intent is None:
            raise LookupError(f"Payment intent {intent_id} not found")

        if intent.status != "created":
            raise ValueError(f"Cannot authorize intent in status '{intent.status}'")

        # Mock PSP authorize — always succeeds
        psp_result = await self._psp.authorize(str(intent_id), intent.amount)
        psp_reference = psp_result["psp_reference"]

        # Update intent
        intent.status = "authorized"
        intent.psp_reference = psp_reference

        # Insert balanced ledger batch
        ledger_svc = LedgerService(self._db)
        await ledger_svc.insert_batch(intent_id, "authorization hold", intent.amount)

        await self._db.commit()

        return {
            "id": str(intent.id),
            "status": intent.status,
            "psp_reference": intent.psp_reference,
            "amount": intent.amount,
            "currency": intent.currency,
            "authorized_at": intent.created_at.isoformat(),  # intent's original created_at
        }
