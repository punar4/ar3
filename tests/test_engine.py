"""End-to-end tests for engine.py, with a fake model (no API calls)."""

import json

import config
from engine import decide
from schemas import Action, FailedPayment, Source


def pay(code, channel="RECURRING", method="UPI", attempt=1, acquirer="ACQ_A"):
    return FailedPayment(payment_id="pay_001", amount_paise=49900, method=method, channel=channel,
                         error_code=code, attempt_number=attempt, acquirer=acquirer)


def model_says(category, action, confidence=0.9, wait=None):
    reply = json.dumps({"category": category, "action": action, "reason": "fake model",
                        "confidence": confidence, "wait_minutes": wait})
    return lambda model, prompt, thinking: reply


def must_not_call(model, prompt, thinking):
    raise AssertionError("Nemotron should not be called for this payment")


def test_known_code_is_decided_by_rules_without_nemotron():
    d = decide(pay("51", method="CARD"), ask=must_not_call)
    assert d.source == Source.RULE
    assert d.action == Action.RETRY_SCHEDULED
    assert d.idempotency_key == "pay_001:attempt-2"


def test_unknown_code_goes_to_nemotron_and_gets_an_alternate_acquirer():
    d = decide(pay("U30", channel="LIVE_CHECKOUT"),
               ask=model_says("GATEWAY_TEMPORARY", "RETRY_ALT_ACQUIRER"))
    assert d.source == Source.LLM_FAST
    assert d.action == Action.RETRY_ALT_ACQUIRER
    assert d.next_acquirer == "ACQ_B"          # not ACQ_A, which just failed


def test_safety_check_overrides_nemotron():
    d = decide(pay("U30", attempt=3), ask=model_says("ISSUER_TEMPORARY", "RETRY_SCHEDULED", wait=60))
    assert d.action == Action.STOP
    assert "retry_cap" in d.overrides
    assert d.idempotency_key is None           # no retry, so no key


def test_rules_only_mode_sends_unknown_codes_to_human_review():
    d = decide(pay("U30"), ask=must_not_call, use_llm=False)
    assert d.action == Action.HUMAN_REVIEW


def test_no_alternate_acquirer_means_prompt_customer(monkeypatch):
    monkeypatch.setattr(config, "ACQUIRERS", ["ACQ_A"])
    d = decide(pay("96", channel="LIVE_CHECKOUT", method="CARD"), ask=must_not_call)
    assert d.action == Action.PROMPT_CUSTOMER
    assert "no_alternate_acquirer" in d.overrides