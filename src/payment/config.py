"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Env-driven application settings.

    Every value has a safe local default.  Override via environment variables
    or a ``.env`` file in the project root.
    """

    # ── Database ──────────────────────────────────────────────────────────
    db_dsn: str = "postgresql+asyncpg://payment:payment@localhost:5432/payment"

    # ── Redis ─────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Idempotency ───────────────────────────────────────────────────────
    idempotency_ttl_seconds: int = 2_592_000  # 30 days

    # ── Outbox ────────────────────────────────────────────────────────────
    outbox_poll_interval_seconds: float = 1.0
    outbox_batch_size: int = 100
    outbox_max_retries: int = 10

    # ── App ───────────────────────────────────────────────────────────────
    app_port: int = 8000
    log_level: str = "info"

    model_config = {"extra": "ignore", "env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
