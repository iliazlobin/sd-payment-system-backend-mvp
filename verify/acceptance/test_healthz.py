"""Health check: GET /healthz returns 200 with status ok."""

from verify.acceptance.conftest import assert_200


def test_healthz_ok(client):
    """Health endpoint returns 200 with status ok."""
    body = assert_200(client.get("/healthz"))
    assert body["status"] == "ok"
