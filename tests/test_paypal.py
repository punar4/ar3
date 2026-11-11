"""PayPal errors go through the same engine: rules, safety checks, retry details. No network calls."""

import pytest

from engine import decide
from paypal_adapter import from_paypal_error, usd_to_paise
from paypal_client import PayPalError
from schemas import Action, Channel, Source


def _err(issue, description="", status=422):
    return PayPalError(status, "UNPROCESSABLE_ENTITY", issue, description, "dbg", {})


def _never_called(*args):
    raise AssertionError("Nemotron should not be called for a known PayPal code")


@pytest.mark.parametrize("issue, channel, expected", [
    ("INSTRUMENT_DECLINED", Channel.LIVE_CHECKOUT, Action.PROMPT_CUSTOMER),
    ("INSTRUMENT_DECLINED", Channel.RECURRING, Action.STOP),
    ("PAYER_ACTION_REQUIRED", Channel.LIVE_CHECKOUT, Action.PROMPT_CUSTOMER),
    ("TRANSACTION_REFUSED", Channel.LIVE_CHECKOUT, Action.STOP),
    ("ORDER_ALREADY_CAPTURED", Channel.LIVE_CHECKOUT, Action.STOP),
    ("DUPLICATE_INVOICE_ID", Channel.RECURRING, Action.STOP),
    ("PAYEE_ACCOUNT_RESTRICTED", Channel.LIVE_CHECKOUT, Action.HUMAN_REVIEW),
    ("INTERNAL_SERVER_ERROR", Channel.RECURRING, Action.RETRY_SCHEDULED),
])
def test_paypal_rules(issue, channel, expected):
    p = from_paypal_error(_err(issue), "ORDER1", "49.99", channel=channel)
    d = decide(p, ask=_never_called)
    assert d.action == expected
    assert d.source == Source.RULE


def test_paypal_glitch_retries_through_paypal_with_request_id():
    p = from_paypal_error(_err("INTERNAL_SERVER_ERROR", status=500), "ORDER2", "20.00")
    d = decide(p, ask=_never_called)
    assert d.action == Action.RETRY_ALT_ACQUIRER
    assert d.next_acquirer == "PAYPAL"
    assert d.idempotency_key == "ORDER2:attempt-2"


def test_paypal_retry_cap_still_applies():
    p = from_paypal_error(_err("INTERNAL_SERVER_ERROR", status=500), "ORDER3", "20.00", attempt_number=3)
    assert decide(p, ask=_never_called).action == Action.STOP


def test_unknown_paypal_code_goes_to_the_model():
    reply = ('{"category": "UNKNOWN", "action": "HUMAN_REVIEW", "reason": "unclear", '
             '"confidence": 0.3, "wait_minutes": null}')
    p = from_paypal_error(_err("SOMETHING_NEW", "Processing failed"), "ORDER4", "10.00")
    d = decide(p, ask=lambda *a: reply)
    assert d.action == Action.HUMAN_REVIEW
    assert d.source != Source.RULE


def test_usd_converted_for_rupee_thresholds():
    assert usd_to_paise("1000.00") == 8_800_000   # ~₹88,000: counts as high value
