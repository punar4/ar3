"""AR3 as an MCP server: any AI shopping agent can ask "my PayPal payment failed, what now?"
Run: python ar3_mcp.py   (stdio transport)"""

from mcp.server.fastmcp import FastMCP

import engine
from paypal_adapter import usd_to_paise
from schemas import Action, Channel, FailedPayment, Method

mcp = FastMCP("ar3")


def agent_instruction(decision: dict) -> str:
    """One plain sentence the agent can follow without reading the whole decision."""
    action = decision["action"]
    key = decision.get("idempotency_key")
    same_id = (f" with the same PayPal-Request-Id: {key}" if decision.get("next_acquirer") == "PAYPAL"
               else f" with idempotency key {key}") if key else ""
    if action == Action.STOP:
        return "Do not retry this payment."
    if action == Action.HUMAN_REVIEW:
        return "Do not retry; tell the user a person will review it."
    if action == Action.PROMPT_CUSTOMER:
        return "Ask the user to fix it or choose another way to pay."
    if action == Action.RETRY_ALT_ACQUIRER:
        return f"Retry once now{same_id}."
    if action == Action.RETRY_SCHEDULED:
        wait = decision.get("wait_minutes")
        when = f"after {wait} minutes" if wait else "later"
        return f"Retry {when}{same_id}."
    return "Do not retry; a person will review it."

@mcp.tool()
def decide_failed_payment(error_code: str, error_description: str = "", method: str = "PAYPAL",
                          channel: str = "LIVE_CHECKOUT", attempt_number: int = 1,
                          amount_usd: str = "10.00", payment_id: str = "agent-payment") -> dict:
    """Call this whenever a payment fails, BEFORE retrying. AR3 diagnoses the failure and says
    whether a retry is safe. Never retry if it says no."""
    pay_method = Method(method.strip().upper())
    pay_channel = Channel(channel.strip().upper())
    is_paypal = pay_method == Method.PAYPAL
    payment = FailedPayment(
        payment_id=payment_id,
        # PayPal reports USD: convert with the adapter, so AR3's rupee thresholds still apply.
        amount_paise=usd_to_paise(amount_usd) if is_paypal else max(1, round(float(amount_usd) * 100)),
        method=pay_method,
        channel=pay_channel,
        error_code=error_code,
        error_description=error_description,
        error_source="PAYPAL" if is_paypal else None,
        attempt_number=attempt_number,
        acquirer="PAYPAL" if is_paypal else None,
    )
    decision = engine.decide(payment).model_dump(mode="json")
    decision["agent_instruction"] = agent_instruction(decision)
    return decision


if __name__ == "__main__":
    mcp.run()
