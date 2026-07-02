"""Refund service — outbox dispatch for refund."""


class RefundService:
    """Handles refund of captured payment intents."""

    def __init__(self, db):
        self._db = db

    async def refund(self, intent_id: str, amount: int | None = None) -> dict | None:
        """Initiate refund for a captured payment intent.

        Returns response dict or None if intent not found / invalid state.
        """
        # Stub — will be implemented by staff task FR4.
        return None
