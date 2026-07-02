"""Ledger service — balanced batch insertion, queries, verification."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from payment.models.ledger_entry import LedgerEntry
from payment.models.payment_intent import PaymentIntent


class LedgerService:
    """Double-entry ledger operations."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def insert_batch(
        self, intent_id: uuid.UUID, description: str, amount: int
    ) -> list[LedgerEntry]:
        """Insert a balanced debit+credit pair for an intent.

        Returns the two LedgerEntry rows (debit, credit).
        """
        batch_id = uuid.uuid4()

        # Compute running balance: the last balance_after for this intent, or 0
        last = await self._db.execute(
            select(LedgerEntry.balance_after)
            .where(LedgerEntry.intent_id == intent_id)
            .order_by(LedgerEntry.created_at.desc())
            .limit(1)
        )
        current_balance = last.scalar() or 0

        # Debit entry — advances the running balance
        debit_balance = current_balance + amount
        debit = LedgerEntry(
            id=uuid.uuid4(),
            intent_id=intent_id,
            batch_id=batch_id,
            side="debit",
            amount=amount,
            balance_after=debit_balance,
            description=description,
        )

        # Credit entry — same balance_after as its paired debit
        credit = LedgerEntry(
            id=uuid.uuid4(),
            intent_id=intent_id,
            batch_id=batch_id,
            side="credit",
            amount=amount,
            balance_after=debit_balance,
            description=description,
        )

        self._db.add_all([debit, credit])
        await self._db.flush()

        return [debit, credit]

    async def get_entries(self, intent_id: uuid.UUID) -> list[dict]:
        """Retrieve all ledger entries for an intent ordered by created_at ASC."""
        result = await self._db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.intent_id == intent_id)
            .order_by(LedgerEntry.created_at.asc())
        )
        entries = result.scalars().all()
        return [
            {
                "side": e.side,
                "amount": e.amount,
                "description": e.description,
                "balance_after": e.balance_after,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]

    async def verify_balance(self, intent_id: uuid.UUID) -> dict | None:
        """Verify the zero-sum ledger invariant for an intent.

        Returns dict with intent_id, debits_total, credits_total, balanced.
        Returns None if intent not found.
        """
        # Check intent exists
        exists = await self._db.get(PaymentIntent, intent_id)
        if exists is None:
            return None

        result = await self._db.execute(
            select(
                func.coalesce(
                    func.sum(LedgerEntry.amount).filter(LedgerEntry.side == "debit"), 0
                ).label("debits"),
                func.coalesce(
                    func.sum(LedgerEntry.amount).filter(LedgerEntry.side == "credit"), 0
                ).label("credits"),
            ).where(LedgerEntry.intent_id == intent_id)
        )
        row = result.one()
        debits_total: int = int(row.debits)
        credits_total: int = int(row.credits)

        return {
            "intent_id": str(intent_id),
            "debits_total": debits_total,
            "credits_total": credits_total,
            "balanced": debits_total == credits_total,
        }

    async def current_balance(self, intent_id: uuid.UUID) -> int:
        """Return the current running balance for an intent (0 if no entries)."""
        last = await self._db.execute(
            select(LedgerEntry.balance_after)
            .where(LedgerEntry.intent_id == intent_id)
            .order_by(LedgerEntry.created_at.desc())
            .limit(1)
        )
        return last.scalar() or 0
