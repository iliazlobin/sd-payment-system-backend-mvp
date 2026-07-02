"""FastAPI application factory, lifespan, and /healthz endpoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from payment.config import settings
from payment.redis import close_redis


# ── Lifespan ────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup / shutdown."""
    # Startup — outbox worker will be started here in a future task.
    yield
    # Shutdown
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

    # ── Routers (registered by subsequent build tasks) ──────────────────
    # from payment.routers import payment_intents, authorize, capture,
    #     refund, webhooks
    # app.include_router(payment_intents.router)
    # app.include_router(authorize.router)
    # app.include_router(capture.router)
    # app.include_router(refund.router)
    # app.include_router(webhooks.router)

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
