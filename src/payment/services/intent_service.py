"""Intent service — create, retrieve, idempotency via Redis."""

import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payment.models.payment_intent import PaymentIntent


class IntentService:
    """Business logic for payment intent CRUD with idempotency."""

    def __init__(self, db: AsyncSession, redis: Redis, ttl_seconds: int = 2_592_000):
        self._db = db
        self._redis = redis
        self._ttl = ttl_seconds

    async def create_intent(
        self, amount: int, currency: str, payment_method: str, idempotency_key: str
    ) -> tuple[dict, int]:
        """Create a payment intent with idempotency check.

        Returns (response_dict, status_code).
        """
        # Stub: always create a new intent.
        intent = PaymentIntent(
            id=uuid.uuid4(),
            idempotency_key=idempotency_key,
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            status="created",
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(intent)
        await self._db.flush()

        result = {
            "id": str(intent.id),
            "idempotency_key": intent.idempotency_key,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
            "payment_method": intent.payment_method,
            "created_at": intent.created_at.isoformat(),
        }
        return result, 201

    async def get_intent(self, intent_id: uuid.UUID) -> dict | None:
        """Retrieve a payment intent by id."""
        result = await self._db.execute(
            select(PaymentIntent).where(PaymentIntent.id == intent_id)
        )
        intent = result.scalar_one_or_none()
        if intent is None:
            return None
        return {
            "id": str(intent.id),
            "idempotency_key": intent.idempotency_key,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
            "payment_method": intent.payment_method,
            "psp_reference": intent.psp_reference,
            "created_at": intent.created_at.isoformat(),
        }
