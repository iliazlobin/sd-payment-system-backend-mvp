"""FR3: View payment intent status and full transaction history.

GET /payment-intents/{id} → 200 with intent fields + ledger_entries array.
Ledger entries show side, amount, description, balance_after, created_at.
Authorization creates a ledger batch (debit + credit).
Non-existent intent → 404.
"""

from verify.acceptance.conftest import (
    assert_404,
    authorize_intent,
    capture_intent,
    create_payment_intent,
    get_intent,
)


def test_get_intent_returns_full_detail(client, fresh_key):
    """GET returns intent with all expected fields."""
    intent = create_payment_intent(client, idempotency_key=fresh_key)

    body = get_intent(client, intent["id"])

    assert body["id"] == intent["id"]
    assert "amount" in body
    assert "currency" in body
    assert "status" in body
    assert "payment_method" in body
    assert "ledger_entries" in body
    assert isinstance(body["ledger_entries"], list)


def test_ledger_entries_after_authorize(client, fresh_key):
    """After authorize, ledger_entries contains a debit+credit pair for authorization hold."""
    intent = create_payment_intent(client, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])

    body = get_intent(client, intent["id"])

    entries = body["ledger_entries"]
    assert len(entries) >= 2, f"Expected at least 2 ledger entries, got {len(entries)}"

    # Should have at least one debit and one credit with authorization hold description
    descriptions = {e["description"] for e in entries}
    assert (
        "authorization hold" in descriptions
    ), f"Expected 'authorization hold' in descriptions: {descriptions}"

    sides = {e["side"] for e in entries}
    assert "debit" in sides
    assert "credit" in sides


def test_ledger_entries_after_authorize_and_capture(client, fresh_key):
    """After authorize+re, ledger contains entries for both authorization hold and capture settlement."""
    intent = create_payment_intent(client, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])
    capture_intent(client, intent["id"])

    import time

    for _ in range(10):
        body = get_intent(client, intent["id"])
        if body["status"] == "captured":
            break
        time.sleep(0.3)

    body = get_intent(client, intent["id"])
    entries = body["ledger_entries"]

    descriptions = {e["description"] for e in entries}
    assert "authorization hold" in descriptions
    assert "capture settlement" in descriptions


def test_balance_after_is_present(client, fresh_key):
    """Every ledger entry includes balance_after."""
    intent = create_payment_intent(client, idempotency_key=fresh_key)
    authorize_intent(client, intent["id"])

    body = get_intent(client, intent["id"])

    for entry in body["ledger_entries"]:
        assert "balance_after" in entry, f"Ledger entry missing balance_after: {entry}"
        assert isinstance(entry["balance_after"], int)


def test_get_nonexistent_intent(client):
    """GET non-existent intent returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/payment-intents/{fake_id}")
    assert_404(r)
