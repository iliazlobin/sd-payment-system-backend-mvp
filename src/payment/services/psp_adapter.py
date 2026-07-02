"""Mock PSP adapter — deterministic responses for MVP.

Always succeeds.  Returns ``psp_{intent_id[:8]}`` as the reference.
"""


class MockPspAdapter:
    """Deterministic mock Payment Service Provider."""

    def generate_reference(self, intent_id: str) -> str:
        """Generate a deterministic PSP reference."""
        return f"psp_{intent_id[:8]}"

    async def authorize(self, intent_id: str, amount: int) -> dict:
        """Mock PSP authorize — always succeeds."""
        return {
            "success": True,
            "psp_reference": self.generate_reference(intent_id),
        }

    async def capture(self, psp_reference: str, amount: int) -> dict:
        """Mock PSP capture — always succeeds."""
        return {"success": True, "psp_reference": psp_reference}

    async def refund(self, psp_reference: str, amount: int) -> dict:
        """Mock PSP refund — always succeeds."""
        return {"success": True, "psp_reference": psp_reference}
