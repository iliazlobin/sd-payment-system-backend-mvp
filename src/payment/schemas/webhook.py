"""Webhook Pydantic schemas."""

from pydantic import BaseModel


class WebhookEventRequest(BaseModel):
    """Incoming webhook event from a PSP."""

    id: str
    type: str
    data: dict | None = None


class WebhookEventResponse(BaseModel):
    """Acknowledge response for webhook events."""

    received: bool
    duplicate: bool = False
