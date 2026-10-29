"""Safety checks: independent rules that can override any decision, from the rule table or Nemotron.

Every check runs on every decision (no elif chain), and every override is recorded.
"""

from collections.abc import Callable

import config
from schemas import Action, Channel, Decision, FailedPayment, FailureCategory

RETRIES = {Action.RETRY_ALT_ACQUIRER, Action.RETRY_SCHEDULED}

# A check returns a changed Decision, or None if the decision is fine.
Check = Callable[[FailedPayment, Decision], Decision | None]


def _override(decision: Decision, check: str, why: str, **changes) -> Decision:
    """Return a copy of the decision with the changes, the reason and the check's name recorded."""
    return decision.model_copy(update={
        **changes,
        "reason": f"{decision.reason} | Safety check '{check}': {why}",
        "overrides": decision.overrides + [check],
    })


def low_confidence(p: FailedPayment, d: Decision) -> Decision | None:
    if d.action != Action.HUMAN_REVIEW and d.confidence < config.CONFIDENCE_THRESHOLD:
        return _override(d, "low_confidence", f"confidence {d.confidence:.2f} is too low",
                         action=Action.HUMAN_REVIEW, wait_minutes=None)
    return None


def risk_never_retried(p: FailedPayment, d: Decision) -> Decision | None:
    if d.category == FailureCategory.RISK and d.action not in {Action.STOP, Action.HUMAN_REVIEW}:
        return _override(d, "risk_never_retried", "possible fraud: never retry or prompt",
                         action=Action.STOP, wait_minutes=None)
    return None


def hard_decline_never_retried(p: FailedPayment, d: Decision) -> Decision | None:
    if d.category == FailureCategory.HARD_DECLINE and d.action in RETRIES:
        return _override(d, "hard_decline_never_retried", "retrying a hard decline never works",
                         action=Action.STOP, wait_minutes=None)
    return None


def alt_acquirer_only_for_gateway_glitch(p: FailedPayment, d: Decision) -> Decision | None:
    if d.action != Action.RETRY_ALT_ACQUIRER:
        return None
    if d.category == FailureCategory.GATEWAY_TEMPORARY and p.channel == Channel.LIVE_CHECKOUT:
        return None
    if p.channel == Channel.RECURRING:
        return _override(d, "alt_acquirer_only_for_gateway_glitch",
                         "only gateway glitches at checkout get an instant retry",
                         action=Action.RETRY_SCHEDULED, wait_minutes=config.MIN_WAIT_MINUTES)
    return _override(d, "alt_acquirer_only_for_gateway_glitch",
                     "only gateway glitches get another acquirer",
                     action=Action.PROMPT_CUSTOMER, wait_minutes=None)


def scheduled_retry_only_for_recurring(p: FailedPayment, d: Decision) -> Decision | None:
    if d.action == Action.RETRY_SCHEDULED and p.channel == Channel.LIVE_CHECKOUT:
        return _override(d, "scheduled_retry_only_for_recurring",
                         "a waiting customer can't be retried later",
                         action=Action.PROMPT_CUSTOMER, wait_minutes=None)
    return None


def prompt_only_when_customer_present(p: FailedPayment, d: Decision) -> Decision | None:
    if d.action == Action.PROMPT_CUSTOMER and p.channel == Channel.RECURRING:
        return _override(d, "prompt_only_when_customer_present",
                         "the customer isn't present on a recurring payment",
                         action=Action.STOP, wait_minutes=None)
    return None


def retry_cap(p: FailedPayment, d: Decision) -> Decision | None:
    if d.action in RETRIES and p.attempt_number >= config.RETRY_CAP:
        return _override(d, "retry_cap", f"attempt {p.attempt_number} reached the cap",
                         action=Action.STOP, wait_minutes=None)
    return None


def minimum_wait(p: FailedPayment, d: Decision) -> Decision | None:
    if d.action != Action.RETRY_SCHEDULED:
        return None
    floor = (config.HIGH_VALUE_MIN_WAIT_MINUTES if p.amount_paise > config.HIGH_VALUE_PAISE
             else config.MIN_WAIT_MINUTES)
    if d.wait_minutes is None or d.wait_minutes < floor:
        return _override(d, "minimum_wait", f"scheduled retries wait at least {floor} minutes",
                         wait_minutes=floor)
    return None


CHECKS: list[Check] = [
    low_confidence,
    risk_never_retried,
    hard_decline_never_retried,
    alt_acquirer_only_for_gateway_glitch,
    scheduled_retry_only_for_recurring,
    prompt_only_when_customer_present,
    retry_cap,
    minimum_wait,
]


def apply_policy(payment: FailedPayment, decision: Decision) -> Decision:
    """Run every check, in order, on the latest version of the decision."""
    for check in CHECKS:
        changed = check(payment, decision)
        if changed is not None:
            decision = changed
    return decision