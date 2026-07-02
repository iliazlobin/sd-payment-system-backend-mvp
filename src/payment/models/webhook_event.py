"""WebhookEvent ORM model — idempotent PSP event storage."""

from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from payment.models.base import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Text, primary_key=True)  # PSP's event id
    psp = Column(String(20), nullable=False)
    type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
