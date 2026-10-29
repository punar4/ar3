"""Rule table: known error codes are decided instantly, with no AI.

Unknown codes return None, which means "ask Nemotron".
"""

from dataclasses import dataclass

from schemas import Action, Channel, Decision, FailedPayment, FailureCategory, Method, Source

ONE_DAY = 24 * 60          # minutes
THREE_DAYS = 3 * ONE_DAY


@dataclass(frozen=True)
class Rule:
    meaning: str                       # what the code means, in plain words
    category: FailureCategory          # the diagnosis
    live_action: Action                # customer present (checkout)
    recurring_action: Action           # customer not present (subscription)
    recurring_wait_minutes: int | None = None   # only for RETRY_SCHEDULED


# Shared rules (several codes mean the same thing)
_RISK = Rule("Lost, stolen or suspected fraud", FailureCategory.RISK, Action.STOP, Action.STOP)
_GATEWAY_GLITCH = Rule("Gateway or acquirer glitch", FailureCategory.GATEWAY_TEMPORARY,
                       Action.RETRY_ALT_ACQUIRER, Action.RETRY_SCHEDULED, 15)

RULES: dict[tuple[Method, str], Rule] = {
    # Cards (ISO 8583 response codes) -
    (Method.CARD, "14"): Rule("Invalid card number", FailureCategory.HARD_DECLINE,
                              Action.PROMPT_CUSTOMER, Action.STOP),
    (Method.CARD, "41"): _RISK,   # lost card
    (Method.CARD, "43"): _RISK,   # stolen card
    (Method.CARD, "51"): Rule("Insufficient funds", FailureCategory.CUSTOMER_ACTION,
                              Action.PROMPT_CUSTOMER, Action.RETRY_SCHEDULED, THREE_DAYS),
    (Method.CARD, "54"): Rule("Expired card", FailureCategory.HARD_DECLINE,
                              Action.PROMPT_CUSTOMER, Action.STOP),
    (Method.CARD, "59"): _RISK,   # suspected fraud
    (Method.CARD, "61"): Rule("Exceeds amount limit", FailureCategory.CUSTOMER_ACTION,
                              Action.PROMPT_CUSTOMER, Action.RETRY_SCHEDULED, ONE_DAY),
    (Method.CARD, "91"): Rule("Issuer bank unavailable", FailureCategory.ISSUER_TEMPORARY,
                              Action.PROMPT_CUSTOMER, Action.RETRY_SCHEDULED, 60),
    (Method.CARD, "96"): _GATEWAY_GLITCH,           # system malfunction
    (Method.CARD, "ACQ_TIMEOUT"): _GATEWAY_GLITCH,
    # UPI (NPCI response codes) -
    (Method.UPI, "Z9"): Rule("Insufficient funds", FailureCategory.CUSTOMER_ACTION,
                             Action.PROMPT_CUSTOMER, Action.RETRY_SCHEDULED, THREE_DAYS),
    (Method.UPI, "ZM"): Rule("Wrong UPI PIN", FailureCategory.CUSTOMER_ACTION,
                             Action.PROMPT_CUSTOMER, Action.STOP),
    (Method.UPI, "Z8"): Rule("Per-transaction limit exceeded", FailureCategory.CUSTOMER_ACTION,
                             Action.PROMPT_CUSTOMER, Action.STOP),
    (Method.UPI, "U69"): Rule("Collect request expired", FailureCategory.CUSTOMER_ACTION,
                              Action.PROMPT_CUSTOMER, Action.STOP),
    (Method.UPI, "ACQ_TIMEOUT"): _GATEWAY_GLITCH,
    # Generic codes like UPI U30 ("debit failed") are left out on purpose:
    # their cause is unclear, so they go to Nemotron.
}


def apply_rules(payment: FailedPayment) -> Decision | None:
    """Decide a known code instantly. Return None if the code is unknown."""
    code = payment.error_code.strip().upper()
    rule = RULES.get((payment.method, code))
    if rule is None:
        return None

    if payment.channel == Channel.LIVE_CHECKOUT:
        action, wait = rule.live_action, None
    else:
        action = rule.recurring_action
        wait = rule.recurring_wait_minutes if action == Action.RETRY_SCHEDULED else None

    return Decision(
        payment_id=payment.payment_id,
        category=rule.category,
        action=action,
        reason=f"Rule: {payment.method} {code} = {rule.meaning}, so {action} for {payment.channel}",
        confidence=1.0,
        source=Source.RULE,
        wait_minutes=wait,
    )