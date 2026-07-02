# Payment System MVP — Build Spec

## 1. Goal & scope

Build a backend MVP implementing the core payment-intent lifecycle: create intents with idempotency,
authorize and capture funds in two phases, refund (partial or full), reconcile every money movement
against a double-entry ledger, and idempotently ingest PSP webhook events. The MVP uses a deterministic
mock PSP adapter in place of Stripe/Adyen, and a polling transactional outbox in place of CDC/Kafka.

**In scope**
- Payment intent creation with two-layer idempotency (Redis response cache + DB unique constraint)
- Two-phase authorize/capture lifecycle with a strict state machine (409 on invalid transitions)
- Asynchronous capture and refund via a transactional outbox + background polling worker
- Partial and full refunds with over-refund validation
- Double-entry ledger: balanced debit+credit batches, denormalized running balance, deferred
  commit-time balance trigger in PostgreSQL
- Per-intent zero-sum ledger verification endpoint
- Idempotent PSP webhook ingestion (event id as primary key) with state-machine advancement
- Health endpoint (`/healthz`)

**Out of scope**
- Real PSP integration (mock adapter returns deterministic responses)
- PCI-DSS compliance / raw card number handling (tokenized payment methods only)
- Multi-currency conversion and forex gain/loss entries
- Dispute / chargeback handling
- Subscription billing with proration
- Redis cluster / replication (single Redis instance)
- Kafka / CDC / Debezium (polling outbox only)

## 2. Functional requirements

- **FR-1 — Create payment intent with idempotency.** Client POSTs `{amount, currency, payment_method}`
  with an `Idempotency-Key` header. First call inserts the intent and caches the response in Redis
  (`idem:{key}`, 30-day TTL); a replay with the same key + body returns the cached response; the same
  key with a different body is rejected.
  `POST /payment-intents` → `201 {id, idempotency_key, amount, currency, status: "created", payment_method, created_at}`;
  replay → `200` (cached); key reuse with different body → `409`; missing header or `amount <= 0` → `422`.
- **FR-2 — Authorize and capture lifecycle.** Authorize is synchronous: mock PSP call, intent →
  `authorized` + `psp_reference`, balanced ledger batch "authorization hold". Capture is asynchronous:
  intent → `capturing` + durable outbox row, then the background worker executes the mock PSP capture,
  advances to `captured`, and writes the "capture settlement" batch.
  `POST /payment-intents/{id}/authorize` → `200 {id, status: "authorized", psp_reference, ...}`;
  `POST /payment-intents/{id}/capture` → `200 {id, status: "capturing", ...}`; wrong state → `409`; unknown id → `404`.
- **FR-3 — View intent status + ledger history.** Full intent detail plus all ledger entries ordered by
  `created_at ASC`, each carrying `balance_after`.
  `GET /payment-intents/{id}` → `200 {..., status, psp_reference, ledger_entries: [...]}`; unknown id → `404`.
- **FR-4 — Refund (partial or full).** Only `captured` intents; optional `amount` for partial refund
  (defaults to full). Outbox dispatch: intent → `refunding`, worker executes the mock PSP refund,
  advances to `refunded`, writes the "refund reversal" batch.
  `POST /payment-intents/{id}/refund {amount?}` → `200 {id, status: "refunding", refund_amount}`;
  non-captured → `409`; over-refund → `422`; unknown id → `404`.
- **FR-5 — Zero-sum ledger verification.** Per-intent invariant check: total debits must equal total credits.
  `GET /payment-intents/{id}/verify` → `200 {intent_id, debits_total, credits_total, balanced: true|false}`; unknown id → `404`.
- **FR-6 — PSP webhook ingestion.** Idempotent by PSP event id (primary key). A matching
  `data.psp_reference` advances the state machine (`payment_intent.succeeded`: capturing → captured;
  `charge.refunded`: refunding → refunded).
  `POST /webhooks/{psp} {id, type, data}` → `200 {received: true}`; duplicate → `200 {received: true, duplicate: true}`;
  unknown psp → `400`; missing `id`/`type` → `422`.

## 3. Stack & deployment

- **Runtime:** Python 3.12, FastAPI, uvicorn
- **Datastore:** PostgreSQL 16 (payment_intents, ledger_entries, webhook_events, outbox) via
  SQLAlchemy 2.0 async + Alembic (single `001_initial` migration, includes the deferred balance trigger)
- **Cache:** Redis 7 (`redis.asyncio`) — idempotency response cache, `idem:{key}`, TTL 30 days
- **Background:** in-process asyncio outbox worker (1s poll, batch 100, `FOR UPDATE SKIP LOCKED`,
  dead-letter after 10 retries)
- **Tests:** pytest + httpx (black-box HTTP acceptance in `verify/acceptance/`, 33 tests)
- **Container:** Docker Compose (`app` + `db` + `redis`, healthchecks on all three, `APP_PORT`/`PG_PORT`/`REDIS_PORT` host overrides)
- **Config:** pydantic-settings, env-driven with safe defaults (`.env` optional; see `.env.example`)

## 4. Data model

```sql
PaymentIntent {
  id:              uuid PK
  idempotency_key: text UNIQUE       ← client-supplied; DB-level idempotency guard
  amount:          integer           ← minor units (cents); never float
  currency:        varchar(3)        ← ISO 4217, default 'usd'
  status:          varchar(20)       ← created | authorized | capturing | captured | refunding | refunded
  psp_reference:   text?             ← mock PSP reference, set on authorization
  payment_method:  varchar(50)       ← tokenized method; never raw PAN
  created_at:      timestamptz
}

LedgerEntry {
  id:             uuid PK
  intent_id:      uuid FK → PaymentIntent (ON DELETE CASCADE)
  batch_id:       uuid               ← groups a balanced debit+credit pair
  side:           varchar(6)         ← debit | credit
  amount:         integer            ← always positive; side determines sign
  balance_after:  integer            ← denormalized running balance
  description:    text               ← 'authorization hold' | 'capture settlement' | 'refund reversal'
  created_at:     timestamptz
}
-- deferred constraint trigger: at commit, per batch_id SUM(debit) must equal SUM(credit)

WebhookEvent {
  id:             text PK            ← the PSP's event id (idempotent ingest)
  psp:            varchar(20)        ← stripe | adyen
  type:           varchar(50)
  payload:        jsonb
  processed_at:   timestamptz?
  created_at:     timestamptz
}

Outbox {
  id:             uuid PK
  event_type:     varchar(30)        ← capture_requested | refund_requested
  payload:        jsonb              ← {intent_id, amount, psp_reference}
  processed_at:   timestamptz?       ← NULL = pending; claimed with FOR UPDATE SKIP LOCKED
  error:          text?
  retry_count:    integer DEFAULT 0  ← dead-lettered at 10
  created_at:     timestamptz
}
```

Redis: `idem:{idempotency_key}` → `{response, _params}` JSON, `EX 2592000` (30 days). `_params` stores
the original request body for reuse-with-different-body (409) detection.

## 5. API

- `GET /healthz` — liveness probe → `{"status":"ok"}`
- `POST /payment-intents` — create intent (requires `Idempotency-Key` header); 201 / 200-replay / 409 / 422
- `GET /payment-intents/{id}` — intent detail + ordered ledger history
- `GET /payment-intents/{id}/verify` — zero-sum ledger check → `{debits_total, credits_total, balanced}`
- `POST /payment-intents/{id}/authorize` — synchronous mock-PSP authorization; ledger batch
- `POST /payment-intents/{id}/capture` — async capture via outbox; returns `capturing`, worker lands `captured`
- `POST /payment-intents/{id}/refund` — async partial/full refund via outbox; returns `refunding`, worker lands `refunded`
- `POST /webhooks/{psp}` — idempotent event ingest (stripe | adyen); advances state machine on matching `psp_reference`

## 6. Test scenarios

- Idempotent create: same key twice → one intent, replayed cached response
- Idempotency conflict: same key with different body → 409
- Validation: missing `Idempotency-Key` → 422; zero/negative amount → 422
- Lifecycle: created → authorized (sync) → capturing → captured (async, polled until the outbox worker lands it)
- State machine: authorize a non-created intent → 409; capture a non-authorized intent → 409; refund a non-captured intent → 409
- Ledger: authorize writes a balanced debit+credit "authorization hold" pair; capture adds "capture settlement"; every entry carries `balance_after`
- Refund: full refund → `refunded` with reversal batch; partial refund honors explicit amount; over-refund → 422
- Invariant: `verify` reports `balanced=true` after authorize, after capture, and after refund; debits total == credits total
- Webhooks: first delivery stored + acknowledged; duplicate event id → `duplicate: true`; unknown psp → 400; missing id → 422; matching `psp_reference` advances intent state
- Not-found handling: unknown intent id → 404 on get/authorize/capture/refund/verify

## 7. Module layout

```
src/payment/
  main.py                  # create_app() factory, lifespan (starts outbox worker), /healthz
  config.py                # pydantic-settings (env-driven, safe defaults)
  database.py              # async SQLAlchemy engine + session factory, get_session
  redis.py                 # async Redis client, get_redis
  models/
    payment_intent.py      # PaymentIntent ORM model
    ledger_entry.py        # LedgerEntry ORM model
    webhook_event.py       # WebhookEvent ORM model
    outbox.py              # Outbox ORM model
  schemas/
    payment_intent.py      # PaymentIntentCreate/Response/Detail
    ledger.py              # LedgerEntryResponse, VerifyLedgerResponse
    webhook.py             # WebhookEventRequest/Response
    refund.py              # RefundRequest/Response
  routers/
    payment_intents.py     # POST /payment-intents, GET /{id}, GET /{id}/verify
    authorize.py           # POST /payment-intents/{id}/authorize
    capture.py             # POST /payment-intents/{id}/capture
    refund.py              # POST /payment-intents/{id}/refund
    webhooks.py            # POST /webhooks/{psp}
  services/
    intent_service.py      # create/get + Redis idempotency (cache, replay, conflict)
    authorize_service.py   # mock PSP authorize + ledger batch
    capture_service.py     # state transition + outbox dispatch
    refund_service.py      # refund validation + outbox dispatch
    ledger_service.py      # balanced batch insertion, history, verify, balance
    webhook_service.py     # idempotent ingest + state machine advancement
    psp_adapter.py         # deterministic mock PSP (authorize/capture/refund)
  workers/
    outbox_worker.py       # asyncio polling worker: claim, PSP call, ledger, dead-letter
alembic/
  versions/001_initial.py  # all four tables + deferred balance trigger
verify/
  manifest.env             # e2e contract (MODE/UP/READY/ACCEPTANCE/DOWN)
  acceptance/              # 7 black-box test files, 33 tests (one file per FR + healthz)
tests/
  conftest.py              # pytest anyio scaffolding for white-box tests
```

## 8. Run

```bash
# Start the stack (Postgres 16 + Redis 7 + app; host port defaults to 8030)
docker compose up -d --build

# Apply migrations
docker compose exec app alembic upgrade head

# Health
curl -sf http://localhost:8030/healthz
# → {"status":"ok"}

# Black-box acceptance suite (33 tests)
pip install httpx pytest
API_BASE_URL="http://localhost:8030" pytest verify/acceptance -v

# Teardown
docker compose down --volumes --remove-orphans
```
