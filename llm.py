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
from schemas import Action, Channel, Decision, FailedPayment, FailureCategory, Source

load_dotenv()
log = logging.getLogger(__name__)

# A function that takes (model, prompt, thinking) and returns the model's raw reply text.
AskFn = Callable[[str, str, bool | None], str]

SYSTEM_PROMPT = """You diagnose failed UPI, card and PayPal payments for AR3, a payment-failure decision engine.
You only recommend. You never move money. Fixed rules and safety checks review your answer.

Pick ONE category:
- HARD_DECLINE: the card or account can't work (invalid, expired, closed). Retrying never helps.
- RISK: lost, stolen or suspected fraud. Never retry.
- CUSTOMER_ACTION: the block is on the customer's side (low balance, wrong PIN, limit reached, request expired).
- ISSUER_TEMPORARY: the customer's bank is down or timing out for now.
- GATEWAY_TEMPORARY: the gateway or acquirer had a temporary glitch.
- UNKNOWN: the cause isn't clear from the information given.

Then answer ONE yes/no question, could_succeed_later:
"If AR3 retried this same payment later, with nobody opening an app or a bank page,
could it go through?"
- true when the blocker can clear on its own over time: money arrives in the account,
  a daily or monthly limit resets, a bank or gateway comes back up. The customer may help
  (by adding money), but no one has to log in, approve or re-enter anything for a retry to work.
- false when a retry can only work after a person actively does something: authenticate (OTP,
  PIN, 3-D Secure), give consent again, approve a new request, or reactivate a cancelled or
  paused mandate or agreement. Also false when nothing can ever fix it (closed account, fraud).
Decide from what the error says is blocking, not from who could speed it up.
You do NOT choose the action. AR3's code picks it from your category, the channel and
could_succeed_later, using the table below.

Rules:
- A vague error (like "transaction failed") is not proof of a hard decline. If the text doesn't show the cause, choose UNKNOWN with HUMAN_REVIEW, or a temporary category with low confidence.
- confidence = how likely your category is correct, from 0 to 1. Be honest. Low confidence is fine.
- Reply with ONLY a JSON object, no other text:
{"category": "...", "could_succeed_later": true, "reason": "one short sentence", "confidence": 0.0, "wait_minutes": null}
wait_minutes: for temporary or money problems, how long before a retry could work (null otherwise).

ACTION TABLE (AR3 applies it in code; it is here so you know what your answer leads to):
- GATEWAY_TEMPORARY: LIVE_CHECKOUT -> RETRY_ALT_ACQUIRER; RECURRING -> RETRY_SCHEDULED.
- ISSUER_TEMPORARY: LIVE_CHECKOUT -> PROMPT_CUSTOMER; RECURRING -> RETRY_SCHEDULED.
- CUSTOMER_ACTION: LIVE_CHECKOUT -> PROMPT_CUSTOMER (the customer is there and can fix it).
  RECURRING -> RETRY_SCHEDULED if could_succeed_later is true;
  STOP if could_succeed_later is false (a person must act and the customer isn't there).
- HARD_DECLINE: LIVE_CHECKOUT -> PROMPT_CUSTOMER (ask for another card or UPI ID); RECURRING -> STOP.
- RISK: always STOP.
- UNKNOWN: always HUMAN_REVIEW.
PAYPAL: the code is a PayPal Orders API error. RETRY_ALT_ACQUIRER means "retry the same PayPal call
safely with the same request id"; PayPal has no other acquirer.

GENERIC DECLINES ARE VAGUE: "Do not honour", "Transaction declined", "Your card was declined"
and similar give no reason. Treat them as UNKNOWN with confidence at most 0.4, not HARD_DECLINE.

Examples:
Input: method=CARD, channel=RECURRING, code=BANK_503, description="Issuer host not reachable, try later"
Output: {"category": "ISSUER_TEMPORARY", "could_succeed_later": true, "reason": "The customer's bank was unreachable, which is usually temporary.", "confidence": 0.85, "wait_minutes": 60}

Input: method=UPI, channel=LIVE_CHECKOUT, code=PG_E102, description="Request timed out at acquirer"
Output: {"category": "GATEWAY_TEMPORARY", "could_succeed_later": true, "reason": "The acquirer timed out; another acquirer may succeed.", "confidence": 0.8, "wait_minutes": null}

Input: method=UPI, channel=RECURRING, code=E999, description="Transaction failed"
Output: {"category": "UNKNOWN", "could_succeed_later": false, "reason": "The error gives no cause, so a person should decide.", "confidence": 0.35, "wait_minutes": null}
"""


class ModelReply(BaseModel):
    """The part of a decision the model fills in. Code adds payment_id and source."""
    category: FailureCategory
    could_succeed_later: bool | None = None   # the question the model answers (Nov 12)
    customer_must_act: bool = False           # older name, still accepted; used only if the above is missing
    action: str | None = None   # ignored: AR3's code picks the action from the category (action_for)
    reason: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    wait_minutes: int | None = Field(default=None, ge=0)

    def must_act(self) -> bool:
        """True when a retry can only work after a person acts (the input action_for needs)."""
        if self.could_succeed_later is not None:
            return not self.could_succeed_later
        return self.customer_must_act


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


DEFAULT_WAIT = {FailureCategory.GATEWAY_TEMPORARY: 15, FailureCategory.ISSUER_TEMPORARY: 60,
                FailureCategory.CUSTOMER_ACTION: 1440}


def action_for(category: FailureCategory, channel: Channel, customer_must_act: bool) -> Action:
    """The action table, in code: the model diagnoses, AR3 decides (same table as rules.py)."""
    live = channel == Channel.LIVE_CHECKOUT
    if category == FailureCategory.RISK:
        return Action.STOP
    if category == FailureCategory.UNKNOWN:
        return Action.HUMAN_REVIEW
    if category == FailureCategory.GATEWAY_TEMPORARY:
        return Action.RETRY_ALT_ACQUIRER if live else Action.RETRY_SCHEDULED
    if live:   # issuer down, customer can fix it, dead card: the customer is there to act
        return Action.PROMPT_CUSTOMER
    if category == FailureCategory.HARD_DECLINE:
        return Action.STOP
    if category == FailureCategory.CUSTOMER_ACTION and customer_must_act:
        return Action.STOP
    return Action.RETRY_SCHEDULED


def _decision(payment: FailedPayment, reply: ModelReply, source: Source, note: str = "",
              confidence: float | None = None) -> Decision:
    action = action_for(reply.category, payment.channel, reply.must_act())
    wait = (reply.wait_minutes or DEFAULT_WAIT.get(reply.category)) if action == Action.RETRY_SCHEDULED else None
    return Decision(
        payment_id=payment.payment_id,
        category=reply.category,
        action=action,
        reason=f"{source}: {reply.reason}" + (f" ({note})" if note else ""),
        confidence=reply.confidence if confidence is None else confidence,
        source=source,
        wait_minutes=wait,
    )


def diagnose(payment: FailedPayment, ask: AskFn = ask_nemotron) -> Decision:
    """Nano -> a second Nano read -> Ultra as tie-breaker -> HUMAN_REVIEW.

    A model's self-reported confidence isn't evidence (N1: same payment, reasoning on vs off,
    opposite answers, both confident). So a confident Nano answer is checked by a second,
    independent read. If the two disagree on the cause, Ultra must side with one of them,
    or a person decides.
    """
    prompt = describe(payment)
    notes: list[str] = []
    candidates: set = set()   # causes proposed by Nano reads that disagreed

    first = _try_tier(ask, config.FAST_MODEL, config.FAST_THINKING, prompt)
    if first is None:
        notes.append(f"{Source.LLM_FAST} gave no valid answer")
    elif first.confidence < config.CONFIDENCE_THRESHOLD:
        notes.append(f"{Source.LLM_FAST} was unsure ({first.confidence:.2f})")
    elif not config.SECOND_READ:
        return _decision(payment, first, Source.LLM_FAST)
    else:
        second = _try_tier(ask, config.FAST_MODEL, not config.FAST_THINKING, prompt)
        if second is not None and second.category == first.category:
            return _decision(payment, first, Source.LLM_FAST, "two independent reads agreed",
                             confidence=min(first.confidence, second.confidence))
        other = second.category if second is not None else "no valid answer"
        notes.append(f"two Nano reads disagreed ({first.category} vs {other})")
        candidates = {first.category} | ({second.category} if second is not None else set())

    ultra = _try_tier(ask, config.ULTRA_MODEL, config.ULTRA_THINKING, prompt)
    if ultra is None:
        notes.append(f"{Source.LLM_ULTRA} gave no valid answer")
    elif ultra.confidence < config.CONFIDENCE_THRESHOLD:
        notes.append(f"{Source.LLM_ULTRA} was unsure ({ultra.confidence:.2f})")
    elif candidates and ultra.category not in candidates:
        notes.append(f"{Source.LLM_ULTRA} gave a third answer ({ultra.category})")
    else:
        return _decision(payment, ultra, Source.LLM_ULTRA,
                         "broke a tie between Nano reads" if candidates else "")

    return Decision(
        payment_id=payment.payment_id,
        category=FailureCategory.UNKNOWN,
        action=Action.HUMAN_REVIEW,
        reason="Sent to human review: " + "; ".join(notes),
        confidence=0.0,
        source=Source.FALLBACK,
    )
