"""actions.py: plans make no calls, execution needs an approver, retries need a request id."""

import pytest

import actions
import paypal_client as pp
from schemas import Action, Decision, FailureCategory, Source

ORDER = {"id": "ORD1", "links": [{"rel": "approve", "href": "https://sandbox/approve"}]}


def _d(action, key=None, wait=None):
    return Decision(payment_id="ORD1", category=FailureCategory.GATEWAY_TEMPORARY, action=action,
                    reason="x", confidence=1.0, source=Source.RULE, idempotency_key=key,
                    wait_minutes=wait)


def test_execute_refuses_without_approver():
    p = actions.plan(_d(Action.STOP), ORDER)
    with pytest.raises(PermissionError):
        actions.execute(p, "ORD1", approved_by=" ")


def test_retry_uses_request_id(monkeypatch):
    seen = {}
    def fake_capture(order_id, request_id=None, mock_error=None):
        seen["request_id"] = request_id
        return {"status": "COMPLETED"}
    monkeypatch.setattr(pp, "capture_order", fake_capture)
    p = actions.plan(_d(Action.RETRY_ALT_ACQUIRER, key="ORD1:attempt-2"), ORDER)
    r = actions.execute(p, "ORD1", approved_by="ops")
    assert r.ok and seen["request_id"] == "ORD1:attempt-2"


def test_retry_without_request_id_is_refused():
    p = actions.plan(_d(Action.RETRY_ALT_ACQUIRER, key=None), ORDER)
    with pytest.raises(ValueError):
        actions.execute(p, "ORD1", approved_by="ops")


def test_paypal_refusal_is_reported_not_raised(monkeypatch):
    def fake_capture(*a, **k):
        raise pp.PayPalError(422, "UNPROCESSABLE_ENTITY", "ORDER_ALREADY_CAPTURED", "", "d", {})
    monkeypatch.setattr(pp, "capture_order", fake_capture)
    p = actions.plan(_d(Action.RETRY_ALT_ACQUIRER, key="ORD1:attempt-2"), ORDER)
    r = actions.execute(p, "ORD1", approved_by="ops")
    assert not r.ok and "ORDER_ALREADY_CAPTURED" in r.summary


def test_prompt_plan_has_buyer_link_and_stop_makes_no_call():
    assert actions.plan(_d(Action.PROMPT_CUSTOMER), ORDER).customer_link == "https://sandbox/approve"
    stop = actions.plan(_d(Action.STOP), ORDER)
    assert stop.paypal_call is None
    assert "No PayPal call" in actions.execute(stop, "ORD1", approved_by="ops").summary
