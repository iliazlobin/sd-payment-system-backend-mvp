"""FR5: Verify every payment matches — zero-sum ledger invariant.

GET /payment-intents/{id}/verify → 200 with debits_total, credits_total, balanced: true|false.
After authorize+capture → balanced=true.
Any intent with ledger entries must balance.
Non-existent intent → 404.
"""

import time

from verify.acceptance.conftest import (
    assert_404,
    authorize_intent,
    capture_intent,
    create_payment_intent,
    get_intent,
    refund_intent,
    verify_ledger,
)


def wait_for_status(client, intent_id, target_status, timeout=5.0):
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


def test_ledger_balanced_after_authorize(client, fresh_key):
    """After authorize, the ledger balances (debits == credits)."""
    intent = create_payment_intent(client, amount=1000, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])

    result = verify_ledger(client, intent["id"])

    assert result["intent_id"] == intent["id"]
    assert "debits_total" in result
    assert "credits_total" in result
    assert result["balanced"] is True, (
        f"Ledger not balanced: debits={result['debits_total']}, "
        f"credits={result['credits_total']}"
    )


def test_ledger_balanced_after_full_flow(client, fresh_key):
    """After authorize+capture+refund, the ledger still balances."""
    intent = create_payment_intent(client, amount=1000, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])
    capture_intent(client, intent["id"])
    wait_for_status(client, intent["id"], "captured")
    refund_intent(client, intent["id"])
    wait_for_status(client, intent["id"], "refunded")

    result = verify_ledger(client, intent["id"])

    assert result["balanced"] is True, (
        f"Ledger not balanced after full flow: debits={result['debits_total']}, "
        f"credits={result['credits_total']}"
    )


def test_ledger_debits_equal_credits(client, fresh_key):
    """Debits total equals credits total after lifecycle."""
    intent = create_payment_intent(client, amount=1500, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])
    capture_intent(client, intent["id"])
    wait_for_status(client, intent["id"], "captured")

    result = verify_ledger(client, intent["id"])

    assert (
        result["debits_total"] == result["credits_total"]
    ), f"debits ({result['debits_total']}) != credits ({result['credits_total']})"


def test_verify_nonexistent_intent(client):
    """Verify on non-existent intent returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/payment-intents/{fake_id}/verify")
    assert_404(r)
