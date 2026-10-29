"""Nemotron diagnosis for failures the rules don't know.

Fast model first -> Ultra if the fast answer is invalid or unsure -> human review if both fail.
The model only recommends; safety checks (policy.py) review every answer.
"""

import logging
import os
from collections.abc import Callable

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

import config
from schemas import Action, Decision, FailedPayment, FailureCategory, Source

load_dotenv()
log = logging.getLogger(__name__)

# A function that takes (model, prompt, thinking) and returns the model's raw reply text.
AskFn = Callable[[str, str, bool | None], str]

SYSTEM_PROMPT = """You diagnose failed UPI and card payments for AR3, a payment-failure decision engine.
You only recommend. You never move money. Fixed rules and safety checks review your answer.

Pick ONE category:
- HARD_DECLINE: the card or account can't work (invalid, expired, closed). Retrying never helps.
- RISK: lost, stolen or suspected fraud. Never retry.
- CUSTOMER_ACTION: the customer must act (low balance, wrong PIN, limit reached, request expired).
- ISSUER_TEMPORARY: the customer's bank is down or timing out for now.
- GATEWAY_TEMPORARY: the gateway or acquirer had a temporary glitch.
- UNKNOWN: the cause isn't clear from the information given.

Pick ONE action:
- RETRY_ALT_ACQUIRER: retry now through another acquirer. Only for GATEWAY_TEMPORARY at LIVE_CHECKOUT.
- RETRY_SCHEDULED: retry later. Only for RECURRING payments. Set wait_minutes.
- PROMPT_CUSTOMER: ask the customer to fix it or use another method. Only at LIVE_CHECKOUT.
- STOP: do not retry.
- HUMAN_REVIEW: you are not sure; a person decides.

Rules:
- A vague error (like "transaction failed") is not proof of a hard decline. If the text doesn't show the cause, choose UNKNOWN with HUMAN_REVIEW, or a temporary category with low confidence.
- confidence = how likely your category is correct, from 0 to 1. Be honest. Low confidence is fine.
- Reply with ONLY a JSON object, no other text:
{"category": "...", "action": "...", "reason": "one short sentence", "confidence": 0.0, "wait_minutes": null}

Examples:
Input: method=CARD, channel=RECURRING, code=BANK_503, description="Issuer host not reachable, try later"
Output: {"category": "ISSUER_TEMPORARY", "action": "RETRY_SCHEDULED", "reason": "The customer's bank was unreachable, which is usually temporary.", "confidence": 0.85, "wait_minutes": 60}

Input: method=UPI, channel=LIVE_CHECKOUT, code=PG_E102, description="Request timed out at acquirer"
Output: {"category": "GATEWAY_TEMPORARY", "action": "RETRY_ALT_ACQUIRER", "reason": "The acquirer timed out; another acquirer may succeed.", "confidence": 0.8, "wait_minutes": null}

Input: method=UPI, channel=RECURRING, code=E999, description="Transaction failed"
Output: {"category": "UNKNOWN", "action": "HUMAN_REVIEW", "reason": "The error gives no cause, so a person should decide.", "confidence": 0.35, "wait_minutes": null}
"""


class ModelReply(BaseModel):
    """The part of a decision the model fills in. Code adds payment_id and source."""
    category: FailureCategory
    action: Action
    reason: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    wait_minutes: int | None = Field(default=None, ge=0)


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Create the API client on first use, so AR3 starts even with no key set."""
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=config.BASE_URL,
            api_key=os.environ["NEBIUS_API_KEY"],
            timeout=config.LLM_TIMEOUT_SECONDS,
            max_retries=1,
        )
    return _client


def ask_nemotron(model: str, prompt: str, thinking: bool | None) -> str:
    """One live, one-shot call to Nemotron on Token Factory. Returns the raw reply text."""
    extra = {}
    if thinking is not None:
        extra["extra_body"] = {"chat_template_kwargs": {"enable_thinking": thinking}}
    response = _get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=config.LLM_MAX_TOKENS,
        **extra,
    )
    return response.choices[0].message.content or ""


def describe(payment: FailedPayment) -> str:
    """Turn a payment into the text the model reads."""
    return (
        f"method={payment.method}, channel={payment.channel}, code={payment.error_code}, "
        f'description="{payment.error_description}", source={payment.error_source}, '
        f"step={payment.error_step}, reason={payment.error_reason}, "
        f"attempt={payment.attempt_number}, amount=₹{payment.amount_paise / 100:.2f}"
    )


def parse_reply(raw: str) -> ModelReply | None:
    """Cut out the JSON object and validate it. Return None if anything is wrong."""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        log.warning("Model reply had no JSON: %r", raw[:200])
        return None
    try:
        return ModelReply.model_validate_json(raw[start:end + 1])
    except ValidationError as error:
        log.warning("Model reply failed validation: %s", error)
        return None


def _try_tier(ask: AskFn, model: str, thinking: bool | None, prompt: str) -> ModelReply | None:
    """One tier, with every failure (timeout, network, bad key, bad JSON) turned into None."""
    try:
        raw = ask(model, prompt, thinking)
    except Exception as error:
        log.warning("Call to %s failed: %s", model, error)
        return None
    return parse_reply(raw)


def diagnose(payment: FailedPayment, ask: AskFn = ask_nemotron) -> Decision:
    """Fast Nemotron -> Ultra if needed -> HUMAN_REVIEW if both fail or are unsure."""
    prompt = describe(payment)
    notes = []
    tiers = [
        (config.FAST_MODEL, config.FAST_THINKING, Source.LLM_FAST),
        (config.ULTRA_MODEL, config.ULTRA_THINKING, Source.LLM_ULTRA),
    ]
    for model, thinking, source in tiers:
        reply = _try_tier(ask, model, thinking, prompt)
        if reply is None:
            notes.append(f"{source} gave no valid answer")
            continue
        if reply.confidence < config.CONFIDENCE_THRESHOLD:
            notes.append(f"{source} was unsure ({reply.confidence:.2f})")
            continue
        return Decision(
            payment_id=payment.payment_id,
            category=reply.category,
            action=reply.action,
            reason=f"{source}: {reply.reason}",
            confidence=reply.confidence,
            source=source,
            wait_minutes=reply.wait_minutes,
        )

    return Decision(
        payment_id=payment.payment_id,
        category=FailureCategory.UNKNOWN,
        action=Action.HUMAN_REVIEW,
        reason="Sent to human review: " + "; ".join(notes),
        confidence=0.0,
        source=Source.FALLBACK,
    )