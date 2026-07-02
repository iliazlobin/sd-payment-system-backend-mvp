"""Authorize service — mock PSP authorize + ledger batch."""

from payment.services.psp_adapter import MockPspAdapter


class AuthorizeService:
    """Handles authorization of payment intents."""

    def __init__(self, db, redis, psp_adapter: MockPspAdapter | None = None):
        self._db = db
        self._redis = redis
        self._psp = psp_adapter or MockPspAdapter()

    async def authorize(self, intent_id: str) -> dict | None:
        """Authorize a payment intent.

        Returns response dict or None if intent not found.
        """
        # Stub — will be implemented by staff task FR2.
        return None
