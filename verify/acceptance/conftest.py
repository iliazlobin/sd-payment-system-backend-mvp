"""Shared fixtures and helpers for the Payment System MVP black-box acceptance suite.

These tests do NOT import `src.payment`. They talk to the running system
via HTTP at API_BASE_URL. Test isolation is achieved through unique
idempotency keys per test — no database clearing required.
"""

import os
import uuid

import httpx
import pytest

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url():
    return API_BASE_URL


@pytest.fixture(scope="session")
def client(base_url):
    """Session-scoped httpx client for the entire acceptance run."""
    with httpx.Client(base_url=base_url, timeout=30) as c:
        yield c


@pytest.fixture
def fresh_key():
    """Unique idempotency key per test for isolation."""
    return f"acceptance-{uuid.uuid4().hex[:16]}"


@pytest.fixture
def fresh_amount():
    """Random payment amount in cents (100–9999) per test."""
    return int.from_bytes(os.urandom(2), "big") % 9900 + 100


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def assert_status(r, expected_status):
    """Assert status and return parsed JSON."""
    assert (
        r.status_code == expected_status
    ), f"Expected {expected_status}, got {r.status_code}: {r.text}"
    if r.status_code == 204:
        return None
    return r.json()


def assert_200(r):
    return assert_status(r, 200)


def assert_201(r):
    return assert_status(r, 201)


def assert_404(r):
    r = assert_status(r, 404)
    assert "detail" in r
    return r


def assert_409(r):
    r = assert_status(r, 409)
    assert "detail" in r
    return r


def assert_422(r):
    r = assert_status(r, 422)
    assert "detail" in r
    return r


# ---------------------------------------------------------------------------
# Setup helpers — create entities via HTTP
# ---------------------------------------------------------------------------


def create_payment_intent(
    client, amount=1000, currency="usd", payment_method="tok_visa", idempotency_key=None
):
    """Create a payment intent and return the parsed response body (201)."""
    if idempotency_key is None:
        idempotency_key = f"setup-{uuid.uuid4().hex[:16]}"
    r = client.post(
        "/payment-intents",
        json={
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method,
        },
        headers={"Idempotency-Key": idempotency_key},
    )
    return assert_201(r)


def authorize_intent(client, intent_id):
    """Authorize a payment intent and return response (200)."""
    r = client.post(f"/payment-intents/{intent_id}/authorize")
    return assert_200(r)


def capture_intent(client, intent_id):
    """Capture a payment intent and return response (200)."""
    r = client.post(f"/payment-intents/{intent_id}/capture")
    return assert_200(r)


def get_intent(client, intent_id):
    """Get payment intent detail with ledger entries."""
    r = client.get(f"/payment-intents/{intent_id}")
    return assert_200(r)


def refund_intent(client, intent_id, amount=None):
    """Refund a payment intent (full or partial)."""
    body = {}
    if amount is not None:
        body["amount"] = amount
    r = client.post(f"/payment-intents/{intent_id}/refund", json=body)
    return assert_200(r)


def verify_ledger(client, intent_id):
    """Verify the zero-sum ledger invariant for an intent."""
    r = client.get(f"/payment-intents/{intent_id}/verify")
    return assert_200(r)


def send_webhook(
    client, psp="stripe", event_id=None, event_type=None, psp_reference=None
):
    """Send a webhook event to the system."""
    if event_id is None:
        event_id = f"evt_{uuid.uuid4().hex}"
    r = client.post(
        f"/webhooks/{psp}",
        json={
            "id": event_id,
            "type": event_type or "payment_intent.succeeded",
            "data": {
                "psp_reference": psp_reference or f"psp_{uuid.uuid4().hex[:8]}",
            },
        },
    )
    return assert_200(r)


def healthz(client):
    """Hit the health check."""
    r = client.get("/healthz")
    return assert_200(r)
