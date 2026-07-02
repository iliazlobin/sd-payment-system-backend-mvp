"""Payment intents router — POST /payment-intents, GET /payment-intents/{id},
GET /payment-intents/{id}/verify."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from payment.database import get_session
from payment.redis import get_redis
from payment.schemas.payment_intent import PaymentIntentCreate
from payment.services.intent_service import (
    IdempotencyConflictError,
    IntentService,
)
from payment.services.ledger_service import LedgerService

router = APIRouter(prefix="/payment-intents", tags=["payment-intents"])


# ── POST /payment-intents ────────────────────────────────────────────────


@router.post("", status_code=201)
async def create_payment_intent(
    body: PaymentIntentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    """Create a payment intent with idempotency."""
    svc = IntentService(db, redis)
    try:
        response, status = await svc.create_intent(
            amount=body.amount,
            currency=body.currency,
            payment_method=body.payment_method,
            idempotency_key=idempotency_key,
        )
        # FastAPI's automatic status_code won't be used since we return
        # different statuses; set it manually via the response
        from starlette.responses import JSONResponse

        return JSONResponse(content=response, status_code=status)
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# ── GET /payment-intents/{id} ────────────────────────────────────────────


@router.get("/{intent_id}")
async def get_payment_intent(
    intent_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    """View payment intent status and full ledger history."""
    svc = IntentService(db, redis)
    result = await svc.get_intent(intent_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Payment intent not found")
    return result


# ── GET /payment-intents/{id}/verify ─────────────────────────────────────


@router.get("/{intent_id}/verify")
async def verify_payment_intent_ledger(
    intent_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Verify the zero-sum ledger invariant for a payment intent."""
    svc = LedgerService(db)
    result = await svc.verify_balance(intent_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Payment intent not found")
    return result
