"""Ledger Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LedgerEntryResponse(BaseModel):
    """Single ledger entry in the response."""

    side: str
    amount: int
    description: str
    balance_after: int
    created_at: datetime


class VerifyLedgerResponse(BaseModel):
    """Response for the ledger verification endpoint."""

    intent_id: UUID
    debits_total: int
    credits_total: int
    balanced: bool
