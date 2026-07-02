"""FR2: Authorize and capture funds for a payment intent.

POST /payment-intents/{id}/authorize → 200, status "authorized", psp_reference set.
POST /payment-intents/{id}/capture → 200, status "captured".
Invalid state transitions → 409.
Non-existent intent → 404.
"""

from verify.acceptance.conftest import (
    assert_404,
    assert_409,
    authorize_intent,
    capture_intent,
    create_payment_intent,
    get_intent,
)


def test_authorize_intent(client, fresh_key):
    """Authorize a created intent returns 200 with psp_reference."""
    intent = create_payment_intent(client, idempotency_key=fresh_key)

    body = authorize_intent(client, intent["id"])

    assert body["status"] == "authorized"
    assert "psp_reference" in body
    assert body["psp_reference"] is not None


def test_capture_intent(client, fresh_key):
    """Capture an authorized intent returns 200 with captured status."""
    intent = create_payment_intent(client, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])

    body = capture_intent(client, intent["id"])

    assert body["status"] in ("capturing", "captured")

    # Verify status advances to captured after outbox worker processes
    import time

    for _ in range(10):
        updated = get_intent(client, intent["id"])
        if updated["status"] == "captured":
            break
        time.sleep(0.3)

    updated = get_intent(client, intent["id"])
    assert (
        updated["status"] == "captured"
    ), f"Expected captured, got {updated['status']} after 3s wait"


def test_authorize_non_created_intent(client, fresh_key):
    """Authorize an already authorized intent returns 409."""
    intent = create_payment_intent(client, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])

    r = client.post(f"/payment-intents/{intent['id']}/authorize")
    assert_409(r)


def test_capture_non_authorized_intent(client, fresh_key):
    """Capture a created (not authorized) intent returns 409."""
    intent = create_payment_intent(client, idempotency_key=fresh_key)

    r = client.post(f"/payment-intents/{intent['id']}/capture")
    assert_409(r)


def test_authorize_nonexistent_intent(client):
    """Authorize non-existent intent returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(f"/payment-intents/{fake_id}/authorize")
    assert_404(r)
