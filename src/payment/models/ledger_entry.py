"""LedgerEntry ORM model — double-entry accounting rows."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from payment.models.base import Base


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_intents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    side = Column(String(6), nullable=False)  # 'debit' or 'credit'
    amount = Column(Integer, nullable=False)  # always positive; side determines sign
    balance_after = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
