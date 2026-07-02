# Deploy Guide — Payment System MVP

## Prerequisites

- Docker Desktop 4.x+ (or Docker Engine 27+ with Compose plugin)
- `curl` (for health checks)
- Git (for checkout)

## From Clean Checkout to Running

```bash
# 1. Clone and enter
git clone https://github.com/iliazlobin/sd-payment-system-backend-mvp.git
cd sd-payment-system-backend-mvp

# 2. Copy default env (optional — all vars have safe defaults)
cp .env.example .env

# 3. Start the stack
APP_PORT=8030 docker compose up -d --build

# 4. Wait for health
until curl -sf http://localhost:8030/healthz; do
  echo "Waiting for app..."; sleep 2
done
echo "App is ready"

# 5. Run database migrations
docker compose exec app alembic upgrade head

# 6. Smoke test
curl -s http://localhost:8030/healthz
# → {"status":"ok"}
```

## Acceptance Tests

Run the black-box acceptance suite against the running stack:

```bash
# Run in verify/.venv to keep host clean
python3 -m venv verify/.venv
source verify/.venv/bin/activate
pip install httpx pytest

API_BASE_URL="http://localhost:8030" pytest verify/acceptance -v
```

Expected output:
```
verify/acceptance/test_healthz.py::test_healthz_ok PASSED
verify/acceptance/test_fr1_create_payment_intent.py::test_create_payment_intent PASSED
... (33 tests total)
```

## Environment Variables

See `.env.example` for all variables. Key ones:

| Variable | Default (container) | Description |
|---|---|---|
| `DB_DSN` | `postgresql+asyncpg://payment:payment@db:5432/payment` | Postgres DSN (in-container) |
| `REDIS_URL` | `redis://redis:6379/0` | Redis URL (in-container) |
| `APP_PORT` | `8000` (container) / `8030` (host) | App listen port |
| `LOG_LEVEL` | `info` | Logging level |
| `PG_PORT` | `5433` (host) | Postgres host port |
| `REDIS_PORT` | `6380` (host) | Redis host port |

Override via environment: `APP_PORT=8010 docker compose up -d`

## Logs

```bash
# Follow app logs
docker compose logs -f app

# All services
docker compose logs

# Last 50 lines
docker compose logs app --tail=50
```

## Migrations

```bash
# Generate a new migration after model changes
docker compose exec app alembic revision --autogenerate -m "description"

# Apply pending migrations
docker compose exec app alembic upgrade head

# Roll back one step
docker compose exec app alembic downgrade -1
```

## Teardown

```bash
# Stop and remove everything (data included)
docker compose down --volumes --remove-orphans
```

To keep data volume for reuse, omit `--volumes`:

```bash
docker compose down --remove-orphans
```

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │ ──→ │  App     │ ──→ │  DB      │
│  (HTTP)  │     │  :8000   │     │  :5432   │
└──────────┘     ├──────────┤     └──────────┘
                 │  Redis   │
                 │  :6379   │
                 └──────────┘
```

Health endpoints: `GET /healthz` → `{"status":"ok"}`
