"""Pydantic request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentIntentCreate(BaseModel):
    """Request body for POST /payment-intents."""

    amount: int = Field(..., gt=0, description="Amount in minor units (cents)")
    currency: str = Field(default="usd", min_length=3, max_length=3)
    payment_method: str = Field(..., min_length=1, max_length=50)


class PaymentIntentResponse(BaseModel):
    """Response body returned on create and single-get."""

    id: UUID
    idempotency_key: str
    amount: int
    currency: str
    status: str
    payment_method: str | None = None
    psp_reference: str | None = None
    created_at: datetime


class PaymentIntentDetail(PaymentIntentResponse):
    """Full detail response including ledger entries."""

    ledger_entries: list["LedgerEntryResponse"] = []
