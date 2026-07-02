"""Capture router — POST /payment-intents/{id}/capture."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from payment.database import get_session
from payment.services.capture_service import CaptureService

router = APIRouter(prefix="/payment-intents", tags=["capture"])


@router.post("/{intent_id}/capture")
async def capture_payment_intent(
    intent_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Capture an authorized payment intent."""
    svc = CaptureService(db)
    try:
        result = await svc.capture(intent_id)
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
