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
    assert ask.calls == [config.FAST_MODEL, config.FAST_MODEL]   # two Nano reads agreed; Ultra never called


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


def test_invented_action_is_ignored_code_picks_the_action():
    bad = reply(0.99, action="REROUTE_TO_CARD")       # v1's flaw: switching the payment method
    ask = fake(fast=bad, ultra=bad)
    d = llm.diagnose(payment(), ask)
    assert d.action == Action.RETRY_SCHEDULED          # ISSUER_TEMPORARY + RECURRING, from the table
    assert d.action != "REROUTE_TO_CARD"


def test_confidence_above_one_is_rejected():
    ask = fake(fast=reply(1.7), ultra=reply(1.7))
    assert llm.diagnose(payment(), ask).action == Action.HUMAN_REVIEW


def test_json_inside_code_fence_is_parsed():
    ask = fake(fast="```json\n" + reply(0.9) + "\n```")
    assert llm.diagnose(payment(), ask).source == Source.LLM_FAST


def test_no_api_client_created_when_using_a_fake():
    llm.diagnose(payment(), fake(fast=reply(0.9)))
    assert llm._client is None                        # starts fine with no key

# ---------- Second read (Nov 12): disagreement = uncertainty ----------
def by_thinking(first, second, ultra=None):
    """Fake model whose Nano answer depends on whether reasoning is on."""
    calls = []

    def ask(model, prompt, thinking):
        calls.append((model, thinking))
        if model == config.ULTRA_MODEL:
            return ultra
        return second if thinking != config.FAST_THINKING else first

    ask.calls = calls
    return ask


def test_disagreeing_reads_go_to_ultra_which_must_pick_one():
    ask = by_thinking(reply(0.9, category="ISSUER_TEMPORARY"), reply(0.9, "STOP", "HARD_DECLINE"),
                      ultra=reply(0.9, "STOP", "HARD_DECLINE"))
    d = llm.diagnose(payment(), ask)
    assert d.source == Source.LLM_ULTRA and d.category == "HARD_DECLINE"
    assert len(ask.calls) == 3


def test_third_different_answer_goes_to_a_person():
    ask = by_thinking(reply(0.9, category="ISSUER_TEMPORARY"), reply(0.9, "STOP", "HARD_DECLINE"),
                      ultra=reply(0.95, "STOP", "RISK"))
    d = llm.diagnose(payment(), ask)
    assert d.action == Action.HUMAN_REVIEW and "disagreed" in d.reason


def test_agreeing_reads_use_the_lower_confidence():
    ask = by_thinking(reply(0.95), reply(0.75))
    assert llm.diagnose(payment(), ask).confidence == 0.75


# ---------- The model diagnoses, the code decides (Nov 12) ----------
def test_customer_must_act_on_recurring_stops():
    r = json.dumps({"category": "CUSTOMER_ACTION", "customer_must_act": True, "reason": "needs 3DS",
                    "confidence": 0.9, "wait_minutes": None})
    assert llm.diagnose(payment(), fake(fast=r)).action == Action.STOP


def test_money_problem_on_recurring_retries_later_with_default_wait():
    r = json.dumps({"category": "CUSTOMER_ACTION", "customer_must_act": False, "reason": "low balance",
                    "confidence": 0.9, "wait_minutes": None})
    d = llm.diagnose(payment(), fake(fast=r))
    assert d.action == Action.RETRY_SCHEDULED and d.wait_minutes == 1440


# ---------- could_succeed_later replaces customer_must_act (Nov 12, later) ----------
def test_could_succeed_later_true_on_recurring_schedules_a_retry():
    r = json.dumps({"category": "CUSTOMER_ACTION", "could_succeed_later": True, "reason": "money may arrive",
                    "confidence": 0.9, "wait_minutes": None})
    d = llm.diagnose(payment(), fake(fast=r))
    assert d.action == Action.RETRY_SCHEDULED and d.wait_minutes == 1440


def test_could_succeed_later_false_on_recurring_stops():
    r = json.dumps({"category": "CUSTOMER_ACTION", "could_succeed_later": False, "reason": "needs consent",
                    "confidence": 0.9, "wait_minutes": None})
    assert llm.diagnose(payment(), fake(fast=r)).action == Action.STOP


def test_new_field_wins_over_old_field():
    r = json.dumps({"category": "CUSTOMER_ACTION", "could_succeed_later": True, "customer_must_act": True,
                    "reason": "x", "confidence": 0.9, "wait_minutes": None})
    assert llm.diagnose(payment(), fake(fast=r)).action == Action.RETRY_SCHEDULED


def test_risk_still_stops_even_if_model_says_it_could_succeed_later():
    r = json.dumps({"category": "RISK", "could_succeed_later": True, "reason": "fraud",
                    "confidence": 0.9, "wait_minutes": None})
    assert llm.diagnose(payment(), fake(fast=r)).action == Action.STOP
