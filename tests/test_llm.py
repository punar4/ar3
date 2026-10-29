"""Tests for llm.py with a fake model: no API calls, no key needed, no cost."""

import json

import config
import llm
from schemas import Action, FailedPayment, Source


def payment():
    return FailedPayment(payment_id="pay_001", amount_paise=49900, method="UPI",
                         channel="RECURRING", error_code="U30", error_description="debit failed")


def reply(confidence=0.9, action="RETRY_SCHEDULED", category="ISSUER_TEMPORARY"):
    return json.dumps({"category": category, "action": action, "reason": "test reason",
                       "confidence": confidence, "wait_minutes": 60})


def fake(fast, ultra=None):
    """A fake model. Each tier returns a fixed reply, or raises it if it's an exception."""
    calls = []

    def ask(model, prompt, thinking):
        calls.append(model)
        answer = fast if model == config.FAST_MODEL else ultra
        if isinstance(answer, Exception):
            raise answer
        return answer

    ask.calls = calls
    return ask


def test_confident_fast_answer_is_used():
    ask = fake(fast=reply(0.9))
    decision = llm.diagnose(payment(), ask)
    assert decision.source == Source.LLM_FAST
    assert ask.calls == [config.FAST_MODEL]          # Ultra never called


def test_garbage_from_fast_escalates_to_ultra():
    ask = fake(fast="Sorry, I can't help with that.", ultra=reply(0.85))
    decision = llm.diagnose(payment(), ask)
    assert decision.source == Source.LLM_ULTRA
    assert ask.calls == [config.FAST_MODEL, config.ULTRA_MODEL]


def test_unsure_fast_answer_escalates_to_ultra():
    ask = fake(fast=reply(0.4), ultra=reply(0.9))
    assert llm.diagnose(payment(), ask).source == Source.LLM_ULTRA


def test_both_tiers_failing_goes_to_human_review():
    ask = fake(fast="not json", ultra=TimeoutError("took too long"))
    decision = llm.diagnose(payment(), ask)
    assert decision.action == Action.HUMAN_REVIEW
    assert decision.source == Source.FALLBACK
    assert decision.confidence == 0.0


def test_timeout_on_both_tiers_goes_to_human_review():
    ask = fake(fast=TimeoutError(), ultra=TimeoutError())
    assert llm.diagnose(payment(), ask).action == Action.HUMAN_REVIEW


def test_invented_action_is_rejected():
    bad = reply(0.99, action="REROUTE_TO_CARD")       # v1's flaw: switching the payment method
    ask = fake(fast=bad, ultra=bad)
    assert llm.diagnose(payment(), ask).action == Action.HUMAN_REVIEW


def test_confidence_above_one_is_rejected():
    ask = fake(fast=reply(1.7), ultra=reply(1.7))
    assert llm.diagnose(payment(), ask).action == Action.HUMAN_REVIEW


def test_json_inside_code_fence_is_parsed():
    ask = fake(fast="```json\n" + reply(0.9) + "\n```")
    assert llm.diagnose(payment(), ask).source == Source.LLM_FAST


def test_no_api_client_created_when_using_a_fake():
    llm.diagnose(payment(), fake(fast=reply(0.9)))
    assert llm._client is None                        # starts fine with no key