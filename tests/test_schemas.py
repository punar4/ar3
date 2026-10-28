"""Tests for schemas.py: bad data must be rejected at the door."""

import pytest
from pydantic import ValidationError

from schemas import Action, Channel, Decision, FailedPayment, FailureCategory, Method, Source


def make_payment(**changes):
    """A valid payment; pass changes to break one field at a time."""
    data = {
        "payment_id": "pay_001",
        "amount_paise": 49900,
        "method": "UPI",
        "channel": "RECURRING",
        "error_code": "U30",
    }
    data.update(changes)
    return FailedPayment(**data)


def test_valid_payment_is_accepted():
    payment = make_payment()
    assert payment.method == Method.UPI
    assert payment.channel == Channel.RECURRING
    assert payment.attempt_number == 1   # default filled in


def test_negative_amount_is_rejected():
    with pytest.raises(ValidationError):
        make_payment(amount_paise=-100)


def test_zero_amount_is_rejected():
    with pytest.raises(ValidationError):
        make_payment(amount_paise=0)


def test_cash_method_is_rejected():
    with pytest.raises(ValidationError):
        make_payment(method="CASH")


def test_confidence_above_one_is_rejected():
    with pytest.raises(ValidationError):
        Decision(
            payment_id="pay_001",
            category=FailureCategory.UNKNOWN,
            action=Action.HUMAN_REVIEW,
            reason="model output",
            confidence=1.7,
            source=Source.LLM_FAST,
        )