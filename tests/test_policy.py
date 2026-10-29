"""Tests for policy.py: one test per safety check, plus two checks firing together."""

from policy import apply_policy
from schemas import Action, Decision, FailedPayment, FailureCategory as C, Source


def pay(channel="RECURRING", attempt=1, amount=49900):
    return FailedPayment(payment_id="p1", amount_paise=amount, method="UPI",
                         channel=channel, error_code="X", attempt_number=attempt)


def dec(category, action, confidence=0.9, wait=None, source=Source.LLM_FAST):
    return Decision(payment_id="p1", category=category, action=action, reason="model said so",
                    confidence=confidence, source=source, wait_minutes=wait)


def test_low_confidence_goes_to_human_review():
    d = apply_policy(pay(), dec(C.GATEWAY_TEMPORARY, Action.RETRY_SCHEDULED, confidence=0.5, wait=60))
    assert d.action == Action.HUMAN_REVIEW and "low_confidence" in d.overrides


def test_risk_is_never_prompted_or_retried():
    d = apply_policy(pay("LIVE_CHECKOUT"), dec(C.RISK, Action.PROMPT_CUSTOMER))
    assert d.action == Action.STOP


def test_hard_decline_is_never_retried():
    d = apply_policy(pay(), dec(C.HARD_DECLINE, Action.RETRY_SCHEDULED, wait=60))
    assert d.action == Action.STOP


def test_alt_acquirer_only_for_gateway_glitch():
    d = apply_policy(pay("LIVE_CHECKOUT"), dec(C.ISSUER_TEMPORARY, Action.RETRY_ALT_ACQUIRER))
    assert d.action == Action.PROMPT_CUSTOMER


def test_scheduled_retry_not_at_live_checkout():
    d = apply_policy(pay("LIVE_CHECKOUT"), dec(C.GATEWAY_TEMPORARY, Action.RETRY_SCHEDULED, wait=15))
    assert d.action == Action.PROMPT_CUSTOMER


def test_no_prompt_when_customer_absent():
    d = apply_policy(pay("RECURRING"), dec(C.CUSTOMER_ACTION, Action.PROMPT_CUSTOMER))
    assert d.action == Action.STOP


def test_retry_cap():
    d = apply_policy(pay(attempt=3), dec(C.ISSUER_TEMPORARY, Action.RETRY_SCHEDULED, wait=60))
    assert d.action == Action.STOP and "retry_cap" in d.overrides


def test_minimum_wait_and_high_value_wait():
    assert apply_policy(pay(), dec(C.ISSUER_TEMPORARY, Action.RETRY_SCHEDULED, wait=5)).wait_minutes == 15
    big = apply_policy(pay(amount=6_000_000), dec(C.ISSUER_TEMPORARY, Action.RETRY_SCHEDULED, wait=5))
    assert big.wait_minutes == 30


def test_two_checks_fire_on_one_payment():
    d = apply_policy(pay("RECURRING", attempt=3),
                     dec(C.GATEWAY_TEMPORARY, Action.RETRY_ALT_ACQUIRER))
    assert d.action == Action.STOP
    assert d.overrides == ["alt_acquirer_only_for_gateway_glitch", "retry_cap"]


def test_safe_rule_decision_is_untouched():
    safe = dec(C.CUSTOMER_ACTION, Action.RETRY_SCHEDULED, confidence=1.0, wait=4320, source=Source.RULE)
    d = apply_policy(pay(), safe)
    assert d == safe and d.overrides == []