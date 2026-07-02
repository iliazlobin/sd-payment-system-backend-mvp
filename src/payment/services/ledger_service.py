"""Ledger service — balanced batch insertion, queries, verification."""


class LedgerService:
    """Double-entry ledger operations."""

    def __init__(self, db):
        self._db = db

    async def get_entries(self, intent_id: str) -> list[dict]:
        """Retrieve all ledger entries for an intent ordered by created_at ASC."""
        # Stub — will be implemented by staff task FR5.
        return []

    async def verify_balance(self, intent_id: str) -> dict | None:
        """Verify the zero-sum ledger invariant for an intent.

        Returns dict with intent_id, debits_total, credits_total, balanced.
        Returns None if intent not found.
        """
        # Stub — will be implemented by staff task FR5.
        return None
