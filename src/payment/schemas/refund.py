"""Refund Pydantic schemas."""

from pydantic import BaseModel, Field


class RefundRequest(BaseModel):
    """Optional request body for refund."""

    amount: int | None = Field(
        default=None, gt=0, description="Partial refund amount in cents"
    )


class RefundResponse(BaseModel):
    """Response for refund."""

    id: str
    status: str
    refund_amount: int | None = None
