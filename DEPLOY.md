# Deploy Guide

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- `curl` (for health checks)

## First Run

```bash
# 1. Start the stack
docker compose up -d --build

# 2. Run database migrations
docker compose exec app alembic upgrade head

# 3. Verify the app is alive
curl -sf http://localhost:8030/healthz
# → {"status":"ok"}

# 4. Run acceptance tests
pip install httpx pytest
API_BASE_URL="http://localhost:8030" pytest verify/acceptance -v
```

## Environment Variables

All config is via environment (see `.env.example`). The main ones:

| Variable       | Default                                        | Description          |
|----------------|------------------------------------------------|----------------------|
| `DB_DSN`       | `postgresql+asyncpg://payment:payment@...:5432/payment` | Postgres DSN |
| `REDIS_URL`    | `redis://localhost:6379/0`                     | Redis URL            |
| `APP_PORT`     | `8000` (container) / `8030` (host)             | App listen port      |
| `LOG_LEVEL`    | `info`                                         | Logging level        |

Overrides via Compose: `APP_PORT=8010 docker compose up -d`

## Teardown

```bash
docker compose down --volumes --remove-orphans
```

## Updating Migrations

```bash
# Generate a new migration after model changes
docker compose exec app alembic revision --autogenerate -m "description"

# Apply pending migrations
docker compose exec app alembic upgrade head
```
