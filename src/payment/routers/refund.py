"""Refund router — POST /payment-intents/{id}/refund."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from payment.database import get_session
from payment.schemas.refund import RefundRequest
from payment.services.refund_service import RefundService

router = APIRouter(prefix="/payment-intents", tags=["refund"])


@router.post("/{intent_id}/refund")
async def refund_payment_intent(
    intent_id: uuid.UUID,
    body: RefundRequest = RefundRequest(),
    db: AsyncSession = Depends(get_session),
):
    """Refund a captured payment intent (partial or full)."""
    svc = RefundService(db)
    try:
        result = await svc.refund(intent_id, amount=body.amount)
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        # Determine if it's a conflict (409) or unprocessable (422)
        msg = str(exc)
        if "status" in msg.lower():
            raise HTTPException(status_code=409, detail=msg) from exc
        raise HTTPException(status_code=422, detail=msg) from exc
