"""FR1: Create a payment intent with amount, currency, payment method, and idempotency key.

POST /payment-intents
→ 201 Created with intent fields.
Idempotency-Key header required → 422 if missing.
Duplicate key returns cached response → 200.
Different body with same key → 409.
"""

from verify.acceptance.conftest import (
    assert_200,
    assert_409,
    assert_422,
    create_payment_intent,
)


def test_create_payment_intent_ok(client, fresh_key, fresh_amount):
    """Create a payment intent returns 201 with all fields."""
    body = create_payment_intent(client, amount=fresh_amount, idempotency_key=fresh_key)

    assert "id" in body
    assert body["amount"] == fresh_amount
    assert body["currency"] == "usd"
    assert body["status"] == "created"
    assert body["payment_method"] == "tok_visa"
    assert body["idempotency_key"] == fresh_key
    assert "created_at" in body


def test_create_payment_intent_missing_idempotency_key(client):
    """Missing Idempotency-Key header returns 422."""
    r = client.post(
        "/payment-intents",
        json={"amount": 1000, "currency": "usd", "payment_method": "tok_visa"},
    )
    assert_422(r)


def test_create_payment_intent_negative_amount(client, fresh_key):
    """Negative amount returns 422."""
    r = client.post(
        "/payment-intents",
        json={"amount": -100, "currency": "usd", "payment_method": "tok_visa"},
        headers={"Idempotency-Key": fresh_key},
    )
    assert_422(r)


def test_create_payment_intent_zero_amount(client, fresh_key):
    """Zero amount returns 422."""
    r = client.post(
        "/payment-intents",
        json={"amount": 0, "currency": "usd", "payment_method": "tok_visa"},
        headers={"Idempotency-Key": fresh_key},
    )
    assert_422(r)


def test_idempotency_duplicate_key_returns_cached(client, fresh_key, fresh_amount):
    """Using the same Idempotency-Key twice returns the cached response."""
    first = create_payment_intent(
        client, amount=fresh_amount, idempotency_key=fresh_key
    )

    # Second request with same key and same body
    r = client.post(
        "/payment-intents",
        json={
            "amount": fresh_amount,
            "currency": "usd",
            "payment_method": "tok_visa",
        },
        headers={"Idempotency-Key": fresh_key},
    )
    second = assert_200(r)

    # Same intent ID returned (not a new one)
    assert second["id"] == first["id"]
    assert second["status"] == first["status"]


def test_idempotency_reuse_key_different_body(client, fresh_key, fresh_amount):
    """Reusing an idempotency key with a different body returns 409."""
    create_payment_intent(client, amount=fresh_amount, idempotency_key=fresh_key)

    # Same key, different amount → conflict
    r = client.post(
        "/payment-intents",
        json={
            "amount": fresh_amount + 500,
            "currency": "usd",
            "payment_method": "tok_visa",
        },
        headers={"Idempotency-Key": fresh_key},
    )
    assert_409(r)


def test_get_intent_not_found(client):
    """GET non-existent payment intent returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/payment-intents/{fake_id}")
    from verify.acceptance.conftest import assert_404

    assert_404(r)
