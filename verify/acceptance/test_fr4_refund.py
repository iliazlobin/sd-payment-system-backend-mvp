"""FR4: Refund a previously captured payment.

POST /payment-intents/{id}/refund → 200, status "refunded".
Full refund: no amount in body → refunds full captured amount.
Partial refund: amount in body → refunds specified amount.
Over-refund → 422.
Refund non-captured intent → 409.
"""

import time

from verify.acceptance.conftest import (
    assert_409,
    assert_422,
    authorize_intent,
    capture_intent,
    create_payment_intent,
    get_intent,
    refund_intent,
)


def wait_for_status(client, intent_id, target_status, timeout=5.0):
    """Poll until intent reaches target status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = get_intent(client, intent_id)
        if body["status"] == target_status:
            return body
        time.sleep(0.3)
    body = get_intent(client, intent_id)
    raise AssertionError(
        f"Expected status '{target_status}', got '{body['status']}' after {timeout}s"
    )


def test_full_refund(client, fresh_key):
    """Full refund on captured intent returns 200 with refunded status."""
    intent = create_payment_intent(client, amount=1000, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])
    capture_intent(client, intent["id"])
    wait_for_status(client, intent["id"], "captured")

    body = refund_intent(client, intent["id"])

    assert body["status"] in ("refunding", "refunded")

    # Wait for outbox to process
    updated = wait_for_status(client, intent["id"], "refunded")
    assert updated["status"] == "refunded"

    # Verify reversal ledger entries exist
    entries = updated["ledger_entries"]
    descriptions = {e["description"] for e in entries}
    assert (
        "refund reversal" in descriptions
    ), f"Expected 'refund reversal' in descriptions: {descriptions}"


def test_partial_refund(client, fresh_key):
    """Partial refund with explicit amount returns 200."""
    intent = create_payment_intent(client, amount=1000, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])
    capture_intent(client, intent["id"])
    wait_for_status(client, intent["id"], "captured")

    body = refund_intent(client, intent["id"], amount=300)

    assert body["status"] in ("refunding", "refunded")


def test_refund_non_captured(client, fresh_key):
    """Refund on authorized (not captured) intent returns 409."""
    intent = create_payment_intent(client, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])

    r = client.post(f"/payment-intents/{intent['id']}/refund", json={})
    assert_409(r)


def test_refund_non_authorized(client, fresh_key):
    """Refund on created (not authorized) intent returns 409."""
    intent = create_payment_intent(client, idempotency_key=fresh_key)

    r = client.post(f"/payment-intents/{intent['id']}/refund", json={})
    assert_409(r)


def test_over_refund(client, fresh_key):
    """Refund amount exceeding captured amount returns 422."""
    intent = create_payment_intent(client, amount=500, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])
    capture_intent(client, intent["id"])
    wait_for_status(client, intent["id"], "captured")

    r = client.post(f"/payment-intents/{intent['id']}/refund", json={"amount": 1000})
    assert_422(r)
