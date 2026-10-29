"""AR3 engine: rules first, then Nemotron, then safety checks.

Returns a recommendation with a reason. AR3 never moves money; the merchant's system carries it out.
"""

import config
from llm import AskFn, ask_nemotron, diagnose
from policy import RETRIES, apply_policy
from rules import apply_rules
from schemas import Action, Decision, FailedPayment, FailureCategory, Source


def _no_rule_decision(payment: FailedPayment) -> Decision:
    """Used in rules-only mode when no rule matches."""
    return Decision(
        payment_id=payment.payment_id,
        category=FailureCategory.UNKNOWN,
        action=Action.HUMAN_REVIEW,
        reason="No rule for this code, and Nemotron is off (rules-only mode)",
        confidence=0.0,
        source=Source.FALLBACK,
    )


def _add_retry_details(payment: FailedPayment, decision: Decision) -> Decision:
    """For retries: add an idempotency key and, for an instant retry, a different acquirer."""
    if decision.action not in RETRIES:
        return decision

    key = f"{payment.payment_id}:attempt-{payment.attempt_number + 1}"

    if decision.action == Action.RETRY_ALT_ACQUIRER:
        others = [a for a in config.ACQUIRERS if a != payment.acquirer]
        if not others:
            return decision.model_copy(update={
                "action": Action.PROMPT_CUSTOMER,
                "reason": f"{decision.reason} | No other acquirer available, so ask the customer",
                "overrides": decision.overrides + ["no_alternate_acquirer"],
            })
        return decision.model_copy(update={"next_acquirer": others[0], "idempotency_key": key})

    return decision.model_copy(update={"idempotency_key": key})


def decide(payment: FailedPayment, ask: AskFn = ask_nemotron, use_llm: bool = True) -> Decision:
    """The whole AR3 flow for one failed payment."""
    decision = apply_rules(payment)                 # 1. known code? decided instantly
    if decision is None:
        decision = diagnose(payment, ask) if use_llm else _no_rule_decision(payment)  # 2. Nemotron
    decision = apply_policy(payment, decision)      # 3. safety checks have the final say
    return _add_retry_details(payment, decision)    # 4. what the merchant needs to act