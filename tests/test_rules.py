"""Tests for rules.py: known codes decided by channel; unknown codes go to Nemotron."""

import pytest

from rules import apply_rules
from schemas import Action, FailedPayment, Source


def make_payment(method, code, channel):
    return FailedPayment(payment_id="pay_001", amount_paise=49900,
                         method=method, channel=channel, error_code=code)


@pytest.mark.parametrize("method, code, channel, expected_action", [
    ("CARD", "51", "LIVE_CHECKOUT", Action.PROMPT_CUSTOMER),
    ("CARD", "51", "RECURRING",     Action.RETRY_SCHEDULED),
    ("CARD", "59", "LIVE_CHECKOUT", Action.STOP),
    ("CARD", "59", "RECURRING",     Action.STOP),
    ("CARD", "54", "LIVE_CHECKOUT", Action.PROMPT_CUSTOMER),
    ("CARD", "54", "RECURRING",     Action.STOP),
    ("CARD", "96", "LIVE_CHECKOUT", Action.RETRY_ALT_ACQUIRER),
    ("CARD", "96", "RECURRING",     Action.RETRY_SCHEDULED),
    ("UPI",  "Z9", "LIVE_CHECKOUT", Action.PROMPT_CUSTOMER),
    ("UPI",  "Z9", "RECURRING",     Action.RETRY_SCHEDULED),
])
def test_known_codes_by_channel(method, code, channel, expected_action):
    decision = apply_rules(make_payment(method, code, channel))
    assert decision.action == expected_action
    assert decision.source == Source.RULE
    assert decision.confidence == 1.0


def test_unknown_code_goes_to_nemotron():
    assert apply_rules(make_payment("UPI", "U30", "RECURRING")) is None


def test_codes_are_per_method():
    assert apply_rules(make_payment("UPI", "51", "RECURRING")) is None   # 51 is a card code


def test_scheduled_retry_has_wait_and_live_has_none():
    recurring = apply_rules(make_payment("CARD", "51", "RECURRING"))
    live = apply_rules(make_payment("CARD", "51", "LIVE_CHECKOUT"))
    assert recurring.wait_minutes == 3 * 24 * 60
    assert live.wait_minutes is None


def test_code_is_normalised():
    assert apply_rules(make_payment("UPI", " z9 ", "RECURRING")) is not None