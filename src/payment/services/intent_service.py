"""Intent service — create, retrieve, idempotency via Redis."""

import json
import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payment.models.payment_intent import PaymentIntent
from payment.services.ledger_service import LedgerService


class IntentService:
    """Business logic for payment intent CRUD with idempotency."""

    IDEMPOTENCY_PREFIX = "idem:"

    def __init__(self, db: AsyncSession, redis: Redis, ttl_seconds: int = 2_592_000):
        self._db = db
        self._redis = redis
        self._ttl = ttl_seconds

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------

    async def create_intent(
        self, amount: int, currency: str, payment_method: str, idempotency_key: str
    ) -> tuple[dict, int]:
        """Create a payment intent with idempotency check.

        Returns (response_dict, status_code).
        """
        cache_key = f"{self.IDEMPOTENCY_PREFIX}{idempotency_key}"

        # 1. Check Redis cache for existing response
        cached = await self._redis.get(cache_key)
        if cached is not None:
            cached_data = json.loads(cached)
            _validate_body_match(
                cached_data["_params"],
                amount,
                currency,
                payment_method,
                idempotency_key,
            )
            # Return the cached response (strip internal _params)
            return cached_data["response"], 200

        # 2. Check DB for existing intent (edge case where Redis missed)
        existing = await self._db.execute(
            select(PaymentIntent).where(
                PaymentIntent.idempotency_key == idempotency_key
            )
        )
        existing_intent = existing.scalar_one_or_none()
        if existing_intent is not None:
            _validate_body_match(
                {
                    "amount": existing_intent.amount,
                    "currency": existing_intent.currency,
                    "payment_method": existing_intent.payment_method,
                },
                amount,
                currency,
                payment_method,
                idempotency_key,
            )
            response = _intent_to_response(existing_intent)
            await _cache_response(
                self._redis,
                cache_key,
                response,
                self._ttl,
                amount,
                currency,
                payment_method,
            )
            return response, 200

        # 3. Create new intent
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
        await self._db.commit()

        response = _intent_to_response(intent)

        # 4. Cache the response in Redis
        await _cache_response(
            self._redis,
            cache_key,
            response,
            self._ttl,
            amount,
            currency,
            payment_method,
        )

        return response, 201

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------

    async def get_intent(self, intent_id: uuid.UUID) -> dict | None:
        """Retrieve a payment intent by id, including ledger entries."""
        result = await self._db.execute(
            select(PaymentIntent).where(PaymentIntent.id == intent_id)
        )
        intent = result.scalar_one_or_none()
        if intent is None:
            return None

        ledger_svc = LedgerService(self._db)
        entries = await ledger_svc.get_entries(intent_id)

        return {
            "id": str(intent.id),
            "idempotency_key": intent.idempotency_key,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
            "payment_method": intent.payment_method,
            "psp_reference": intent.psp_reference,
            "created_at": intent.created_at.isoformat(),
            "ledger_entries": entries,
        }


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------


class IdempotencyConflictError(Exception):
    """Raised when an idempotency key is reused with different body."""


def _intent_to_response(intent: PaymentIntent) -> dict:
    """Serialize a PaymentIntent ORM object to a response dict."""
    return {
        "id": str(intent.id),
        "idempotency_key": intent.idempotency_key,
        "amount": intent.amount,
        "currency": intent.currency,
        "status": intent.status,
        "payment_method": intent.payment_method,
        "created_at": intent.created_at.isoformat(),
    }


async def _cache_response(
    redis: Redis,
    cache_key: str,
    response: dict,
    ttl: int,
    amount: int,
    currency: str,
    payment_method: str,
) -> None:
    """Cache a response along with its request parameters for validation."""
    payload = {
        "response": response,
        "_params": {
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method,
        },
    }
    await redis.set(cache_key, json.dumps(payload), ex=ttl)


def _validate_body_match(
    stored: dict,
    amount: int,
    currency: str,
    payment_method: str,
    idempotency_key: str,
) -> None:
    """Raise IdempotencyConflictError if the new body doesn't match."""
    if (
        stored["amount"] != amount
        or stored["currency"] != currency
        or stored["payment_method"] != payment_method
    ):
        raise IdempotencyConflictError(
            f"Idempotency key '{idempotency_key}' already used "
            f"with different parameters"
        )
