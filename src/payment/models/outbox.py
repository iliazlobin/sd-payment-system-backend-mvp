"""Outbox ORM model — durable async PSP call queue."""

import uuid

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from payment.models.base import Base


class Outbox(Base):
    __tablename__ = "outbox"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(30), nullable=False, index=True)
    payload = Column(JSONB, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
