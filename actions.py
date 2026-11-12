"""Turns an AR3 decision into a planned PayPal action, and runs it only after a person approves.

AR3 never acts alone: plan() is free and safe; execute() needs a named approver.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import paypal_client as pp
from schemas import Action, Decision


@dataclass
class Plan:
    action: Action
    title: str                     # plain words for the screen
    paypal_call: str | None        # the exact PayPal call, shown before approval
    request_id: str | None = None  # PayPal-Request-Id: makes the call safe to repeat
    customer_link: str | None = None
    run_at: str | None = None      # for scheduled retries (ISO time)


@dataclass
class Result:
    ok: bool
    summary: str
    approved_by: str
    at: str
    paypal_status: int | None = None
    paypal_response: dict = field(default_factory=dict)


def plan(decision: Decision, order: dict) -> Plan:
    """What AR3 would do for this order. Makes no PayPal calls."""
    order_id = order["id"]
    a = decision.action
    if a == Action.RETRY_ALT_ACQUIRER:
        return Plan(a, "Retry the capture now, safely",
                    f"POST /v2/checkout/orders/{order_id}/capture",
                    request_id=decision.idempotency_key)
    if a == Action.RETRY_SCHEDULED:
        when = datetime.now(timezone.utc) + timedelta(minutes=decision.wait_minutes or 15)
        return Plan(a, f"Retry the capture in {decision.wait_minutes} minutes",
                    f"POST /v2/checkout/orders/{order_id}/capture (scheduled)",
                    request_id=decision.idempotency_key, run_at=when.isoformat(timespec="minutes"))
    if a == Action.PROMPT_CUSTOMER:
        return Plan(a, "Send the buyer back to PayPal to fix it or pick another way to pay",
                    f"GET /v2/checkout/orders/{order_id} (check status, then share the link)",
                    customer_link=pp.approve_link(order))
    if a == Action.STOP:
        return Plan(a, "Stop: don't retry this payment", None)
    return Plan(a, "Send to a person for review", None)


def execute(p: Plan, order_id: str, approved_by: str, mock_error: str | None = None) -> Result:
    """Run the plan. Refuses without an approver. mock_error only exists for sandbox demos."""
    if not approved_by.strip():
        raise PermissionError("AR3 only acts after a named person approves")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    try:
        if p.action == Action.RETRY_ALT_ACQUIRER:
            if not p.request_id:
                raise ValueError("refusing to retry without a PayPal-Request-Id")
            resp = pp.capture_order(order_id, request_id=p.request_id, mock_error=mock_error)
            return Result(True, f"PayPal capture: {resp.get('status')}", approved_by, now, 201, resp)
        if p.action == Action.PROMPT_CUSTOMER:
            resp = pp.get_order(order_id)
            return Result(True, f"Order is {resp.get('status')}; link ready for the buyer",
                          approved_by, now, 200, resp)
    except pp.PayPalError as e:
        return Result(False, f"PayPal refused: {e.issue}", approved_by, now, e.status, e.raw)

    if p.action == Action.RETRY_SCHEDULED:
        return Result(True, f"Retry scheduled for {p.run_at} (same request id)", approved_by, now)
    if p.action == Action.STOP:
        return Result(True, "Stopped. No PayPal call made", approved_by, now)
    return Result(True, "Added to the review queue. No PayPal call made", approved_by, now)
