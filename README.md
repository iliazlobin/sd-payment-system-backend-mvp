# Payment System MVP

[![lint](https://github.com/iliazlobin/sd-payment-system-backend-mvp/actions/workflows/lint.yml/badge.svg)](https://github.com/iliazlobin/sd-payment-system-backend-mvp/actions/workflows/lint.yml)
[![ci](https://github.com/iliazlobin/sd-payment-system-backend-mvp/actions/workflows/ci.yml/badge.svg)](https://github.com/iliazlobin/sd-payment-system-backend-mvp/actions/workflows/ci.yml)
[![functional](https://github.com/iliazlobin/sd-payment-system-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-payment-system-backend-mvp/actions/workflows/functional.yml)

Core payment lifecycle backend — create intents, authorize, capture, refund, reconcile against a double-entry ledger, and process PSP webhook events. One FastAPI process, PostgreSQL 16 for the ledger, Redis 7 for the idempotency cache.

## Quick Start

```bash
# 1. Start the full stack (Postgres + Redis + App)
docker compose up -d --build

# 2. Run database migrations
docker compose exec app alembic upgrade head

# 3. Verify it's alive
curl -sf http://localhost:8030/healthz
# → {"status":"ok"}
```

The default host port is `8030`. Override with `APP_PORT=8010 docker compose up -d`.

## Run Acceptance Tests

```bash
pip install httpx pytest
API_BASE_URL="http://localhost:8030" pytest verify/acceptance -v
```

33 black-box tests covering all 6 functional requirements, the health check, state machine transitions, and the ledger invariant.

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Health check — returns `{"status":"ok"}` |
| `POST` | `/payment-intents` | Create a payment intent (requires `Idempotency-Key` header) |
| `GET` | `/payment-intents/{id}` | View intent status + ledger history |
| `POST` | `/payment-intents/{id}/authorize` | Authorize funds |
| `POST` | `/payment-intents/{id}/capture` | Capture authorized funds |
| `POST` | `/payment-intents/{id}/refund` | Refund a captured payment (partial or full) |
| `GET` | `/payment-intents/{id}/verify` | Verify the zero-sum ledger invariant |
| `POST` | `/webhooks/{psp}` | Receive PSP webhook events (stripe, adyen) |

## Architecture

```
┌─────────────┐     ┌─────────────────────────────────┐     ┌──────────────┐
│   Client    │────→│      FastAPI App — :8000         │────→│  PostgreSQL  │
│   (HTTP)    │     │                                  │     │    16        │
└─────────────┘     │  Routers → Services → Models     │     │  ledger      │
                    │                                  │     │  + outbox    │
                    │  + Background Outbox Worker      │     └──────────────┘
                    │    polls every 1s                │           │
                    │                                  │     ┌──────────────┐
                    │  Idempotency cache               │────→│   Redis 7    │
                    └─────────────────────────────────┘     │  idempotency │
                                                           └──────────────┘
```

### Request flow

1. **`POST /payment-intents`** — IntentService checks Redis idempotency cache (`SET NX`). Cache hit → replay response. Cache miss → insert into Postgres, cache response in Redis, return `201`.
2. **`POST /payment-intents/{id}/authorize`** — AuthorizeService calls the mock PSP, updates intent to `authorized`, writes a balanced ledger batch (debit + credit, `"authorization hold"`).
3. **`POST /payment-intents/{id}/capture`** — CaptureService writes an outbox row (`capture_requested`) and returns immediately. The background Outbox Worker polls the outbox table every 1s, executes the mock PSP capture, writes a settlement ledger batch, and advances status to `captured`.
4. **`POST /payment-intents/{id}/refund`** — RefundService writes an outbox row (`refund_requested`). The Outbox Worker calls the mock PSP refund and writes a reversal ledger batch.

### Ledger invariant

Every ledger write inserts a balanced debit+credit pair within the same transaction. A deferred PostgreSQL constraint trigger verifies at commit time that `SUM(amount) WHERE side='debit'` = `SUM(amount) WHERE side='credit'` per `batch_id`. The `GET /payment-intents/{id}/verify` endpoint exposes this as an API.

## Functional Requirements

| FR | Description |
|----|-------------|
| FR1 | Create payment intent with idempotency (Redis `SET NX` + DB unique constraint) |
| FR2 | Two-phase authorize/capture lifecycle with outbox-based async execution |
| FR3 | View intent status and full ledger transaction history |
| FR4 | Partial and full refunds via outbox dispatch |
| FR5 | Zero-sum ledger verification (debits must equal credits) |
| FR6 | PSP webhook ingestion with idempotent processing |

## Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Container | Docker Compose |
| Validation | Pydantic v2 |

## Project Layout

```
src/payment/
├── main.py              # create_app() factory, lifespan, /healthz
├── config.py            # pydantic-settings (env-driven)
├── database.py          # async SQLAlchemy engine, session factory
├── redis.py             # async Redis client
├── models/              # SQLAlchemy ORM models
│   ├── payment_intent.py
│   ├── ledger_entry.py
│   ├── webhook_event.py
│   └── outbox.py
├── schemas/             # Pydantic request/response DTOs
│   ├── payment_intent.py
│   ├── ledger.py
│   ├── webhook.py
│   └── refund.py
├── routers/             # FastAPI routers (thin HTTP layer)
│   ├── payment_intents.py
│   ├── authorize.py
│   ├── capture.py
│   ├── refund.py
│   └── webhooks.py
├── services/            # Business logic
│   ├── intent_service.py
│   ├── authorize_service.py
│   ├── capture_service.py
│   ├── refund_service.py
│   ├── ledger_service.py
│   ├── webhook_service.py
│   └── psp_adapter.py
└── workers/             # Background tasks
    └── outbox_worker.py
verify/
├── manifest.env         # e2e-verify contract
└── acceptance/          # 7 black-box test files (33 tests)
tests/
└── conftest.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_DSN` | `postgresql+asyncpg://payment:payment@db:5432/payment` | Postgres DSN (in-container) |
| `REDIS_URL` | `redis://redis:6379/0` | Redis URL (in-container) |
| `APP_PORT` | `8000` | App listen port |
| `LOG_LEVEL` | `info` | Logging level |
| `IDEMPOTENCY_TTL_SECONDS` | `2592000` | Idempotency cache TTL (30 days) |
| `OUTBOX_POLL_INTERVAL_SECONDS` | `1.0` | Outbox worker poll interval |
| `OUTBOX_BATCH_SIZE` | `100` | Max rows per poll cycle |
| `OUTBOX_MAX_RETRIES` | `10` | Max retries before dead-lettering |

All variables have safe defaults. Override via `.env` or environment. See `.env.example`.

## Out of Scope (MVP)

- Real PSP integration (mock adapter returns deterministic responses)
- PCI-DSS compliance / raw card number handling
- Multi-currency conversion and forex gain/loss entries
- Dispute / chargeback handling
- Subscription billing with proration
- Redis cluster / replication
- Kafka / CDC / Debezium
