"""Capture service — outbox dispatch for capture."""


class CaptureService:
    """Handles capture of authorized payment intents via outbox."""

    def __init__(self, db):
        self._db = db

    async def capture(self, intent_id: str) -> dict | None:
        """Initiate capture for a payment intent.

        Returns response dict or None if intent not found.
        """
        # Stub — will be implemented by staff task FR2.
        return None
