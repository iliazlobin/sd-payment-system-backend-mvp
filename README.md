# Payment System MVP

Core payment lifecycle backend — create intents, authorize, capture, refund, reconcile against a double-entry ledger, and process PSP webhooks.

## Stack

| Component      | Technology                     |
|----------------|--------------------------------|
| API            | FastAPI (Python 3.12)          |
| Database       | PostgreSQL 16                  |
| Cache          | Redis 7                        |
| ORM            | SQLAlchemy 2.0 (async)         |
| Migrations     | Alembic                        |
| Container      | Docker Compose                 |

## Quick Start

```bash
# Start the full stack
docker compose up -d --build

# Run acceptance tests
pip install httpx pytest
API_BASE_URL="http://localhost:8030" pytest verify/acceptance -q

# Tear down
docker compose down --volumes
```

## API Endpoints

| Method | Path                              | Description                          |
|--------|-----------------------------------|--------------------------------------|
| GET    | `/healthz`                        | Health check                         |
| POST   | `/payment-intents`                | Create a payment intent              |
| GET    | `/payment-intents/{id}`           | View intent + ledger history         |
| POST   | `/payment-intents/{id}/authorize` | Authorize funds                      |
| POST   | `/payment-intents/{id}/capture`   | Capture authorized funds             |
| POST   | `/payment-intents/{id}/refund`    | Refund a captured payment            |
| GET    | `/payment-intents/{id}/verify`    | Verify ledger invariant              |
| POST   | `/webhooks/{psp}`                 | Receive PSP webhook events           |

## Functional Requirements

- **FR1:** Create payment intent with idempotency
- **FR2:** Authorize and capture lifecycle
- **FR3:** View intent status + ledger history
- **FR4:** Partial/full refunds
- **FR5:** Zero-sum ledger verification
- **FR6:** PSP webhook ingestion

## Project Layout

```
src/payment/           → Application package
  main.py              → create_app() factory, /healthz, lifespan
  config.py            → pydantic-settings
  database.py          → async SQLAlchemy engine/session
  redis.py             → async Redis client
  models/              → ORM models
  schemas/             → Pydantic DTOs
  routers/             → HTTP layer (thin)
  services/            → Business logic
  workers/             → Background tasks (outbox)
verify/                → Black-box acceptance tests
  manifest.env         → e2e-verify contract
  acceptance/          → Per-FR test files
tests/                 → White-box unit/integration tests
```
