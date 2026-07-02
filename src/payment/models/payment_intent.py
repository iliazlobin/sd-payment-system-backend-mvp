"""PaymentIntent ORM model."""

import uuid

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from payment.models.base import Base


class PaymentIntent(Base):
    __tablename__ = "payment_intents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key = Column(Text, unique=True, nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # minor units (cents)
    currency = Column(String(3), nullable=False, default="usd")
    status = Column(
        String(20),
        nullable=False,
        default="created",
        index=True,
    )
    psp_reference = Column(Text, nullable=True)
    payment_method = Column(String(50), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
