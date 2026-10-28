"""Data shapes for AR3: what a failed payment looks like, and what a decision looks like."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


#enums: the fixed lists of allowed values

class Channel(StrEnum):
    """Where the payment happened. Decides which actions are allowed."""
    LIVE_CHECKOUT = "LIVE_CHECKOUT"  # customer is present, right now
    RECURRING = "RECURRING"          # subscription / autopay, customer = not present


class Method(StrEnum):
    """How the customer tried to pay."""
    UPI = "UPI"
    CARD = "CARD"
    NETBANKING = "NETBANKING"


class FailureCategory(StrEnum):
    """Why the payment failed: the diagnosis."""
    HARD_DECLINE = "HARD_DECLINE"            # card invalid or expired: retrying never works
    RISK = "RISK"                            # lost, stolen or suspected fraud: never retry
    CUSTOMER_ACTION = "CUSTOMER_ACTION"      # low balance, wrong PIN, limit hit: customer must act
    ISSUER_TEMPORARY = "ISSUER_TEMPORARY"    # customer's bank is down for now
    GATEWAY_TEMPORARY = "GATEWAY_TEMPORARY"  # gateway or acquirer glitch for now
    UNKNOWN = "UNKNOWN"                      # cause not clear


class Action(StrEnum):
    """The safe next step AR3 recommends."""
    RETRY_ALT_ACQUIRER = "RETRY_ALT_ACQUIRER"  # retry now through a different acquirer
    RETRY_SCHEDULED = "RETRY_SCHEDULED"        # retry later (recurring only)
    PROMPT_CUSTOMER = "PROMPT_CUSTOMER"        # ask the customer to fix it or use another method
    STOP = "STOP"                              # do not retry
    HUMAN_REVIEW = "HUMAN_REVIEW"              # unsure: a person decides


class Source(StrEnum):
    """Who made the decision. Shown as a badge in the demo."""
    RULE = "RULE"            # the rule table
    LLM_FAST = "LLM_FAST"    # fast Nemotron model
    LLM_ULTRA = "LLM_ULTRA"  # Nemotron Ultra
    FALLBACK = "FALLBACK"    # something failed, safe default used


# What comes in :

class FailedPayment(BaseModel):
    """One failed payment, as it arrives from the gateway (webhook, CSV row or demo preset)."""

    payment_id: str = Field(min_length=1)
    amount_paise: int = Field(gt=0)          # money in paise: ₹499.00 = 49900
    method: Method
    channel: Channel
    error_code: str = Field(min_length=1)    # e.g. "51" (card) or "U30" (UPI)
    error_description: str = ""              # the gateway's message text, often vague
    error_source: str | None = None          # gateway fields: who reported the failure
    error_step: str | None = None            #   which step of the payment failed
    error_reason: str | None = None          #   the gateway's short reason label
    attempt_number: int = Field(default=1, ge=1)   # 1 = first try, 2 = first retry, ...
    acquirer: str | None = None              # which acquirer processed this attempt
    failed_at: datetime | None = None        # when it failed


# What goes out :

class Decision(BaseModel):
    """AR3's recommendation for one failed payment. AR3 never moves money; it only recommends."""

    payment_id: str
    category: FailureCategory
    action: Action
    reason: str = Field(min_length=1)               # why, in plain words; every decision explains itself
    confidence: float = Field(ge=0.0, le=1.0)       # 0.0 = guessing, 1.0 = certain (rules use 1.0)
    source: Source
    wait_minutes: int | None = Field(default=None, ge=0)   # only for RETRY_SCHEDULED
    overrides: list[str] = Field(default_factory=list)     # safety checks that changed the decision