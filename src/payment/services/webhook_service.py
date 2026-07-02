"""Webhook service — idempotent ingest, state machine advancement."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payment.models.payment_intent import PaymentIntent
from payment.models.webhook_event import WebhookEvent


VALID_PSPS = frozenset({"stripe", "adyen"})


class WebhookService:
    """Handles incoming PSP webhook events."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def ingest_event(
        self, psp: str, event_id: str, event_type: str, data: dict | None
    ) -> dict:
        """Idempotently ingest a webhook event.

        Returns response dict with received and optional duplicate flag.
        Raises ValueError if psp is unknown.
        """
        if psp not in VALID_PSPS:
            raise ValueError(f"Unknown PSP: '{psp}'")

        # Check for duplicate
        existing = await self._db.get(WebhookEvent, event_id)
        if existing is not None:
            return {"received": True, "duplicate": True}

        # Insert new event — idempotent by primary key
        event = WebhookEvent(
            id=event_id,
            psp=psp,
            type=event_type,
            payload=data or {},
            processed_at=None,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(event)

        # Try to match psp_reference and advance state machine
        if data and "psp_reference" in data:
            psp_ref = data["psp_reference"]
            result = await self._db.execute(
                select(PaymentIntent).where(PaymentIntent.psp_reference == psp_ref)
            )
            intent = result.scalar_one_or_none()
            if intent is not None:
                if (
                    event_type == "payment_intent.succeeded"
                    and intent.status == "capturing"
                ):
                    intent.status = "captured"
                elif event_type == "charge.refunded" and intent.status == "refunding":
                    intent.status = "refunded"

        await self._db.commit()

        return {"received": True}
