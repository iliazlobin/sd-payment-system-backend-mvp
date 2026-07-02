"""Authorize router — POST /payment-intents/{id}/authorize."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from payment.database import get_session
from payment.services.authorize_service import AuthorizeService

router = APIRouter(prefix="/payment-intents", tags=["authorize"])


@router.post("/{intent_id}/authorize")
async def authorize_payment_intent(
    intent_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Authorize a payment intent."""
    svc = AuthorizeService(db)
    try:
        result = await svc.authorize(intent_id)
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
