"""The MCP tool is called directly here: same function an agent reaches over MCP, no transport.

Known error codes, so the rule table answers and no model (or network) is involved.
"""

from ar3_mcp import decide_failed_payment


def test_refused_payment_is_not_retried():
    d = decide_failed_payment("TRANSACTION_REFUSED")
    assert d["action"] == "STOP"
    assert "Do not retry" in d["agent_instruction"]


def test_server_glitch_retries_through_paypal_with_request_id():
    d = decide_failed_payment("INTERNAL_SERVER_ERROR", error_description="Internal Server Error")
    assert d["action"] == "RETRY_ALT_ACQUIRER"
    assert "PayPal-Request-Id" in d["agent_instruction"]
    assert d["idempotency_key"] in d["agent_instruction"]
