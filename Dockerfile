# ── Builder stage ───────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Runtime stage ──────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

COPY --from=builder /root/.local /root/.local

WORKDIR /app

COPY src/ src/
COPY alembic.ini alembic/ alembic/

EXPOSE 8000

CMD ["uvicorn", "payment.main:app", "--host", "0.0.0.0", "--port", "8000"]
