"""Mock PSP adapter — deterministic responses for MVP."""


class MockPspAdapter:
    """Deterministic mock Payment Service Provider.

    Always succeeds. Returns ``psp_{intent_id[:8]}`` as the reference.
    """

    def generate_reference(self, intent_id: str) -> str:
        """Generate a deterministic PSP reference."""
        return f"psp_{intent_id[:8]}"
