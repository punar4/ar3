"""Turns a PayPal error into AR3's FailedPayment, so the same engine decides PayPal failures."""

from datetime import datetime, timezone

import config
from paypal_client import PayPalError
from schemas import Channel, FailedPayment, Method


def usd_to_paise(amount_usd: str) -> int:
    """AR3's thresholds are in paise; convert at the approximate rate in config."""
    return max(1, round(float(amount_usd) * config.USD_TO_INR * 100))


def from_paypal_error(err: PayPalError, order_id: str, amount_usd: str,
                      channel: Channel = Channel.LIVE_CHECKOUT, attempt_number: int = 1,
                      step: str = "CAPTURE") -> FailedPayment:
    """One failed PayPal call -> one FailedPayment for engine.decide()."""
    return FailedPayment(
        payment_id=order_id,
        amount_paise=usd_to_paise(amount_usd),
        method=Method.PAYPAL,
        channel=channel,
        error_code=err.issue,                 # e.g. INSTRUMENT_DECLINED
        error_description=err.description,    # PayPal's message; Nemotron reads this if no rule
        error_source="PAYPAL",
        error_step=step,
        error_reason=err.name,                # e.g. UNPROCESSABLE_ENTITY
        attempt_number=attempt_number,
        acquirer="PAYPAL",
        failed_at=datetime.now(timezone.utc),
    )
