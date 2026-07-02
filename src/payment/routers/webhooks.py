"""Webhook router — POST /webhooks/{psp}."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from payment.database import get_session
from payment.schemas.webhook import WebhookEventRequest
from payment.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{psp}")
async def receive_webhook(
    psp: str,
    body: WebhookEventRequest,
    db: AsyncSession = Depends(get_session),
):
    """Receive and idempotently process a PSP webhook event."""
    svc = WebhookService(db)
    try:
        result = await svc.ingest_event(
            psp=psp,
            event_id=body.id,
            event_type=body.type,
            data=body.data,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
