"""T13: build AR3's labelled test set (150 failed payments).

30 known cases come straight from the rule table (every code x both channels).
120 messy cases are hand-written: codes the rules don't know, so Nemotron must diagnose them.
Run: python make_testset.py  ->  writes data/test_cases.json
"""
import json
from collections import Counter
from pathlib import Path

from rules import RULES
from schemas import Action, Channel, FailedPayment, FailureCategory, Method

# Short names so the table below stays readable
UPI, CARD, NB = Method.UPI, Method.CARD, Method.NETBANKING
L, R = Channel.LIVE_CHECKOUT, Channel.RECURRING
GT, IT, CA = FailureCategory.GATEWAY_TEMPORARY, FailureCategory.ISSUER_TEMPORARY, FailureCategory.CUSTOMER_ACTION
HD, RISK, UNK = FailureCategory.HARD_DECLINE, FailureCategory.RISK, FailureCategory.UNKNOWN
ALT, SCHED, PROMPT = Action.RETRY_ALT_ACQUIRER, Action.RETRY_SCHEDULED, Action.PROMPT_CUSTOMER
STOP, HUMAN = Action.STOP, Action.HUMAN_REVIEW

# Labelling rules (same logic as AR3's design):
#   gateway glitch  -> live: retry another acquirer | recurring: retry later
#   issuer down     -> live: ask customer           | recurring: retry later
#   customer action -> live: ask customer           | recurring: retry later if money/limit, stop if they must act
#   hard decline    -> live: ask customer (new card)| recurring: stop
#   risk            -> stop, always
#   too vague       -> human review
#   attempt 3+      -> any retry becomes stop (asking the customer is still allowed)

# (method, channel, code, description, category, expected action, attempt)
MESSY = [
    # --- Gateway / acquirer glitches (22) ---
    (UPI, L, "PG_TIMEOUT", "Gateway timed out waiting for PSP response", GT, ALT, 1),
    (UPI, R, "PG_TIMEOUT", "Gateway timed out waiting for PSP response", GT, SCHED, 1),
    (CARD, L, "PG_E102", "Payment gateway internal error, please retry", GT, ALT, 1),
    (CARD, R, "PG_E102", "Payment gateway internal error, please retry", GT, SCHED, 1),
    (UPI, L, "PSP_UNAVAILABLE", "PSP server not reachable", GT, ALT, 1),
    (CARD, L, "ACQ_502", "Acquirer returned HTTP 502 Bad Gateway", GT, ALT, 1),
    (CARD, R, "ACQ_502", "Acquirer returned HTTP 502 Bad Gateway", GT, SCHED, 1),
    (CARD, L, "ACQ_CONN_RESET", "Connection reset by acquirer host", GT, ALT, 1),
    (UPI, L, "GW_RATE_LIMIT", "Too many requests to PSP, throttled by gateway", GT, ALT, 1),
    (UPI, R, "GW_RATE_LIMIT", "Too many requests to PSP, throttled by gateway", GT, SCHED, 1),
    (CARD, L, "3DS_SERVER_ERR", "3DS server error at acquirer, authentication not started", GT, ALT, 1),
    (NB, L, "NB_GW_TIMEOUT", "Aggregator timed out before reaching the bank", GT, ALT, 1),
    (NB, R, "NB_GW_TIMEOUT", "Aggregator timed out before reaching the bank", GT, SCHED, 1),
    (UPI, L, "PSP_5XX", "PSP returned 503 Service Unavailable", GT, ALT, 1),
    (UPI, R, "PSP_5XX", "PSP returned 503 Service Unavailable", GT, SCHED, 1),
    (CARD, L, "ACQ_SOCKET_TIMEOUT", "Socket read timeout from acquiring bank", GT, ALT, 1),
    (CARD, R, "ACQ_SOCKET_TIMEOUT", "Socket read timeout from acquiring bank", GT, SCHED, 1),
    (UPI, L, "COLLECT_PUSH_FAIL", "Gateway failed to push collect request to PSP", GT, ALT, 1),
    (CARD, L, "GW_INTERNAL", "Internal server error at payment gateway", GT, ALT, 1),
    (CARD, R, "GW_INTERNAL", "Internal server error at payment gateway", GT, SCHED, 1),
    (UPI, L, "PSP_DNS_FAIL", "Gateway could not resolve PSP host", GT, ALT, 1),
    (CARD, L, "ACQ_MAINT", "Acquirer under scheduled maintenance", GT, ALT, 1),

    # --- Issuer / remitter bank temporarily down (20) ---
    (UPI, L, "BANK_503", "Remitter bank CBS not available", IT, PROMPT, 1),
    (UPI, R, "BANK_503", "Remitter bank CBS not available", IT, SCHED, 1),
    (UPI, L, "XY", "Remitter CBS offline", IT, PROMPT, 1),
    (UPI, R, "XY", "Remitter CBS offline", IT, SCHED, 1),
    (UPI, L, "RB_TIMEOUT", "Remitter bank did not respond in time", IT, PROMPT, 1),
    (UPI, R, "RB_TIMEOUT", "Remitter bank did not respond in time", IT, SCHED, 1),
    (CARD, L, "ISS_UNAVAIL", "Issuer or switch inoperative", IT, PROMPT, 1),
    (CARD, R, "ISS_UNAVAIL", "Issuer or switch inoperative", IT, SCHED, 1),
    (CARD, L, "ISS_TIMEOUT", "Issuer did not respond to authorisation request", IT, PROMPT, 1),
    (CARD, R, "ISS_TIMEOUT", "Issuer did not respond to authorisation request", IT, SCHED, 1),
    (NB, L, "NB_BANK_DOWN", "Bank's netbanking site is down for maintenance", IT, PROMPT, 1),
    (NB, R, "NB_BANK_DOWN", "Bank's netbanking site is down for maintenance", IT, SCHED, 1),
    (UPI, L, "BANK_MAINT", "Payer bank under scheduled downtime", IT, PROMPT, 1),
    (UPI, R, "BANK_MAINT", "Payer bank under scheduled downtime", IT, SCHED, 1),
    (CARD, L, "ISS_SYS_ERR", "System malfunction at issuing bank", IT, PROMPT, 1),
    (CARD, R, "ISS_SYS_ERR", "System malfunction at issuing bank", IT, SCHED, 1),
    (UPI, L, "RB_CBS_ERR", "Remitter bank core banking error, try after some time", IT, PROMPT, 1),
    (UPI, R, "RB_CBS_ERR", "Remitter bank core banking error, try after some time", IT, SCHED, 1),
    (NB, L, "NB_503", "Bank server busy, please try later", IT, PROMPT, 1),
    (CARD, R, "ISS_BUSY", "Issuer busy, retry later", IT, SCHED, 1),

    # --- Customer can fix it (22) ---
    (UPI, L, "INSUFF_BAL", "Payer account has insufficient balance", CA, PROMPT, 1),
    (UPI, R, "INSUFF_BAL", "Payer account has insufficient balance", CA, SCHED, 1),
    (UPI, R, "MANDATE_BAL", "Mandate execution failed: balance insufficient", CA, SCHED, 1),
    (NB, R, "NSF", "Not sufficient funds in the linked account", CA, SCHED, 1),
    (CARD, L, "LOW_FUNDS", "Insufficient credit limit on card", CA, PROMPT, 1),
    (CARD, R, "LOW_FUNDS", "Insufficient credit limit on card", CA, SCHED, 1),
    (UPI, L, "WRONG_PIN", "Incorrect UPI PIN entered", CA, PROMPT, 1),
    (UPI, L, "PIN_TRIES", "Number of PIN tries exceeded", CA, PROMPT, 1),
    (UPI, L, "TXN_DECLINED_BY_USER", "Customer declined the collect request", CA, PROMPT, 1),
    (UPI, L, "COLLECT_EXPIRED", "Collect request expired, payer did not approve", CA, PROMPT, 1),
    (UPI, R, "MANDATE_PAUSED", "Customer has paused the AutoPay mandate", CA, STOP, 1),
    (UPI, L, "DAILY_LIMIT", "Payer has exceeded daily UPI transaction limit", CA, PROMPT, 1),
    (UPI, R, "DAILY_LIMIT", "Payer has exceeded daily UPI transaction limit", CA, SCHED, 1),
    (CARD, L, "OTP_FAILED", "OTP authentication failed", CA, PROMPT, 1),
    (CARD, L, "3DS_ABANDONED", "Customer closed the 3D Secure page", CA, PROMPT, 1),
    (CARD, L, "OTP_TIMEOUT", "OTP not entered within time", CA, PROMPT, 1),
    (NB, L, "NB_USER_CANCEL", "User cancelled at bank login page", CA, PROMPT, 1),
    (NB, L, "NB_LOW_BAL", "Insufficient balance in account", CA, PROMPT, 1),
    (CARD, R, "LIMIT_EXCEEDED", "Card's spending limit exceeded for the month", CA, SCHED, 1),
    (CARD, L, "CVV_MISMATCH", "Incorrect CVV entered", CA, PROMPT, 1),
    (UPI, L, "APP_TIMEOUT", "Customer did not complete payment in UPI app", CA, PROMPT, 1),
    (UPI, R, "BAL_LOW_AUTOPAY", "AutoPay debit failed: account balance too low", CA, SCHED, 1),

    # --- Hard declines: this card/account won't work (16) ---
    (CARD, L, "INV_CARD", "Card number is not valid", HD, PROMPT, 1),
    (CARD, R, "INV_CARD", "Card number is not valid", HD, STOP, 1),
    (CARD, L, "CARD_EXPIRED", "Card has expired", HD, PROMPT, 1),
    (CARD, R, "CARD_EXPIRED", "Card has expired", HD, STOP, 1),
    (CARD, L, "ACCT_CLOSED", "Account linked to card is closed", HD, PROMPT, 1),
    (CARD, R, "ACCT_CLOSED", "Account linked to card is closed", HD, STOP, 1),
    (UPI, L, "INV_VPA", "Invalid VPA, account does not exist", HD, PROMPT, 1),
    (UPI, R, "MANDATE_REVOKED", "Mandate has been revoked by the customer", HD, STOP, 1),
    (UPI, R, "VPA_DEACTIVATED", "UPI ID is no longer active", HD, STOP, 1),
    (UPI, L, "ACCT_DORMANT", "Remitter account is dormant", HD, PROMPT, 1),
    (UPI, R, "ACCT_DORMANT", "Remitter account is dormant", HD, STOP, 1),
    (CARD, L, "TXN_NOT_PERMITTED", "Transaction not permitted to cardholder", HD, PROMPT, 1),
    (CARD, R, "TXN_NOT_PERMITTED", "Transaction not permitted to cardholder", HD, STOP, 1),
    (NB, L, "NB_ACCT_CLOSED", "Account closed", HD, PROMPT, 1),
    (NB, R, "NB_ACCT_CLOSED", "Account closed", HD, STOP, 1),
    (CARD, R, "CARD_REPLACED", "Card has been replaced, old card number no longer valid", HD, STOP, 1),

    # --- Risk / fraud: never retry (12) ---
    (CARD, L, "FRAUD_SUSPECT", "Transaction flagged as suspected fraud by issuer", RISK, STOP, 1),
    (CARD, R, "FRAUD_SUSPECT", "Transaction flagged as suspected fraud by issuer", RISK, STOP, 1),
    (CARD, L, "STOLEN", "Card reported stolen", RISK, STOP, 1),
    (UPI, L, "RISK_BLOCK", "Payment blocked by PSP risk engine", RISK, STOP, 1),
    (UPI, R, "RISK_BLOCK", "Payment blocked by PSP risk engine", RISK, STOP, 1),
    (UPI, L, "VELOCITY", "Velocity check failed: too many attempts in short time", RISK, STOP, 1),
    (CARD, L, "RISK_SCORE", "High risk score from merchant fraud screening", RISK, STOP, 1),
    (CARD, R, "GW_FRAUD", "Gateway fraud rule triggered", RISK, STOP, 1),
    (UPI, L, "SUSP_PAYER", "Payer VPA on suspicious list", RISK, STOP, 1),
    (NB, L, "NB_RISK", "Bank declined: suspicious activity on account", RISK, STOP, 1),
    (CARD, L, "LOST_CARD", "Card reported lost, pick up card", RISK, STOP, 1),
    (UPI, R, "AML_HOLD", "Transaction held for compliance review", RISK, STOP, 1),

    # --- Too vague to call: send to a human (16) ---
    (UPI, L, "U30", "debit failed", UNK, HUMAN, 1),
    (UPI, R, "U30", "debit failed", UNK, HUMAN, 1),
    (UPI, R, "U30", "Debit has been failed", UNK, HUMAN, 1),
    (CARD, L, "05", "Do not honour", UNK, HUMAN, 1),
    (CARD, R, "05", "Do not honour", UNK, HUMAN, 1),
    (UPI, L, "ERR_GENERIC", "Something went wrong", UNK, HUMAN, 1),
    (NB, L, "NB_ERR", "Transaction failed", UNK, HUMAN, 1),
    (UPI, R, "UNKNOWN_ERR", "Payment could not be processed", UNK, HUMAN, 1),
    (CARD, L, "DECLINED", "Transaction declined", UNK, HUMAN, 1),
    (CARD, R, "DECLINED", "Transaction declined", UNK, HUMAN, 1),
    (UPI, L, "TXN_FAIL", "", UNK, HUMAN, 1),
    (NB, R, "NB_FAILED", "Failed", UNK, HUMAN, 1),
    (CARD, L, "ERR_01", "Error", UNK, HUMAN, 1),
    (UPI, L, "PAYMENT_FAILED", "Payment failed", UNK, HUMAN, 1),
    (CARD, L, "GENERIC_DECLINE", "Your card was declined", UNK, HUMAN, 1),
    (UPI, R, "X1", "Failure", UNK, HUMAN, 1),

    # --- Retry cap: attempt 3 or later (12) ---
    (UPI, R, "PG_TIMEOUT", "Gateway timed out waiting for PSP response", GT, STOP, 3),
    (CARD, L, "PG_E102", "Payment gateway internal error, please retry", GT, STOP, 3),
    (CARD, L, "ACQ_502", "Acquirer returned HTTP 502 Bad Gateway", GT, STOP, 3),
    (UPI, L, "GW_RATE_LIMIT", "Too many requests to PSP, throttled by gateway", GT, STOP, 3),
    (UPI, R, "BANK_503", "Remitter bank CBS not available", IT, STOP, 3),
    (CARD, R, "ISS_TIMEOUT", "Issuer did not respond to authorisation request", IT, STOP, 3),
    (UPI, R, "RB_TIMEOUT", "Remitter bank did not respond in time", IT, STOP, 5),
    (UPI, R, "INSUFF_BAL", "Payer account has insufficient balance", CA, STOP, 3),
    (NB, R, "NSF", "Not sufficient funds in the linked account", CA, STOP, 3),
    (CARD, R, "LOW_FUNDS", "Insufficient credit limit on card", CA, STOP, 4),
    (CARD, L, "ISS_UNAVAIL", "Issuer or switch inoperative", IT, PROMPT, 3),   # asking isn't a retry
    (UPI, L, "INSUFF_BAL", "Payer account has insufficient balance", CA, PROMPT, 3),
]

AMOUNTS = [49900, 129900, 19900, 6_000_000]   # ₹499, ₹1,299, ₹199, ₹60,000 (high value)


def known_cases():
    """Every rule-table code x both channels, labelled by the rule itself."""
    rows = []
    for (method, code), rule in RULES.items():
        for channel in (L, R):
            action = rule.live_action if channel == L else rule.recurring_action
            rows.append(("known", method, channel, code, rule.meaning, rule.category, action, 1))
    return rows


def build():
    # Safety net: a "messy" code must not be in the rule table, or rules would answer it
    clashes = [(m, c) for m, _, c, *_ in MESSY if (m, c.strip().upper()) in RULES]
    assert not clashes, f"These messy codes are in the rule table: {clashes}"

    rows = known_cases() + [("messy", *row) for row in MESSY]
    cases = []
    for i, (kind, method, channel, code, desc, category, action, attempt) in enumerate(rows):
        case = {
            "kind": kind,
            "payment_id": f"tc_{i + 1:03d}",
            "amount_paise": AMOUNTS[i % len(AMOUNTS)],
            "method": method,
            "channel": channel,
            "error_code": code,
            "error_description": desc,
            "attempt_number": attempt,
            "acquirer": "ACQ_A",
            "expected_category": category,
            "expected_action": action,
        }
        payment_fields = {k: v for k, v in case.items() if k in FailedPayment.model_fields}
        FailedPayment(**payment_fields)   # crash now if any case is malformed
        cases.append(case)
    return cases


if __name__ == "__main__":
    cases = build()
    Path("data").mkdir(exist_ok=True)
    Path("data/test_cases.json").write_text(json.dumps(cases, indent=2, default=str), encoding="utf-8")

    messy = [c for c in cases if c["kind"] == "messy"]
    print(f"Wrote {len(cases)} cases ({len(cases) - len(messy)} known, {len(messy)} messy) to data/test_cases.json")
    print("Messy by category:", dict(Counter(str(c["expected_category"]) for c in messy)))
    print("Messy by method:  ", dict(Counter(str(c["method"]) for c in messy)))
    print("Messy by channel: ", dict(Counter(str(c["channel"]) for c in messy)))