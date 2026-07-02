"""Webhook service — idempotent ingest, state machine advancement."""


class WebhookService:
    """Handles incoming PSP webhook events."""

    def __init__(self, db):
        self._db = db

    async def ingest_event(
        self, psp: str, event_id: str, event_type: str, data: dict | None
    ) -> dict:
        """Idempotently ingest a webhook event.

        Returns response dict with received and optional duplicate flag.
        """
        # Stub — will be implemented by staff task FR6.
        return {"received": True}
