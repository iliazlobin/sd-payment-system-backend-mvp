"""FastAPI application factory, lifespan, and /healthz endpoint."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from payment.config import settings
from payment.database import async_session_factory
from payment.redis import close_redis
from payment.workers.outbox_worker import OutboxWorker

# ── Global outbox worker reference ───────────────────────────────────────

_outbox_worker: OutboxWorker | None = None


# ── Lifespan ────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup / shutdown."""
    global _outbox_worker

    # Startup — start outbox worker as background task
    _outbox_worker = OutboxWorker(
        db_session_factory=async_session_factory,
        poll_interval=settings.outbox_poll_interval_seconds,
        batch_size=settings.outbox_batch_size,
        max_retries=settings.outbox_max_retries,
    )
    worker_task = asyncio.create_task(_outbox_worker.start())

    yield

    # Shutdown
    if _outbox_worker is not None:
        await _outbox_worker.stop()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await close_redis()


# ── Factory ─────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Build and return a configured FastAPI application."""
    app = FastAPI(
        title="Payment System MVP",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── Health check ────────────────────────────────────────────────────
    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    # ── Routers ─────────────────────────────────────────────────────────
    from payment.routers import (
        authorize,
        capture,
        payment_intents,
        refund,
        webhooks,
    )

    app.include_router(payment_intents.router)
    app.include_router(authorize.router)
    app.include_router(capture.router)
    app.include_router(refund.router)
    app.include_router(webhooks.router)

    return app


# ── Entry point ─────────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "payment.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        log_level=settings.log_level,
    )
