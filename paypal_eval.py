"""Tests Nemotron on PayPal failures that the rule table does NOT know. Uses Nebius credits.

python paypal_eval.py            # 31 cases, one run each (~40 model calls)
python paypal_eval.py --runs 3   # same cases 3 times: also measures how consistent Nemotron is

Labels were written before any model run (a held-out set). Saves results/paypal_eval.md and .json.
"""

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import config
from engine import decide
from paypal_adapter import usd_to_paise
from policy import RETRIES
from rules import RULES
from schemas import Action, Channel, FailedPayment, Method

L, R = Channel.LIVE_CHECKOUT, Channel.RECURRING
A = Action
# (code, PayPal-style description, channel, attempt, expected category, expected action)
CASES = [
    # Gateway / PayPal-side glitches: safe to retry (live: now, recurring: later)
    ("PROCESSOR_TIMEOUT", "Timed out waiting for the card processor; no funds were captured", L, 1, "GATEWAY_TEMPORARY", A.RETRY_ALT_ACQUIRER),
    ("GATEWAY_502", "Bad gateway between PayPal and the processor, temporary", R, 1, "GATEWAY_TEMPORARY", A.RETRY_SCHEDULED),
    ("RATE_LIMIT_REACHED", "Too many requests. Try again shortly", L, 1, "GATEWAY_TEMPORARY", A.RETRY_ALT_ACQUIRER),
    ("HTTP_504", "Upstream request timed out", R, 1, "GATEWAY_TEMPORARY", A.RETRY_SCHEDULED),
    ("HTTP_503", "Service temporarily unavailable, retry later", L, 3, "GATEWAY_TEMPORARY", A.STOP),  # retry cap
    ("PROCESSOR_TIMEOUT", "Processor did not respond in time", R, 3, "GATEWAY_TEMPORARY", A.STOP),     # retry cap
    # Buyer's bank down for now
    ("9100", "ISSUER_UNAVAILABLE: card issuer system is down", L, 1, "ISSUER_TEMPORARY", A.PROMPT_CUSTOMER),
    ("ISSUER_TIMEOUT", "No response from the buyer's bank", R, 1, "ISSUER_TEMPORARY", A.RETRY_SCHEDULED),
    ("9100", "Issuer or switch inoperative", R, 1, "ISSUER_TEMPORARY", A.RETRY_SCHEDULED),
    ("BANK_SYSTEM_DOWN", "The buyer's bank is undergoing maintenance", L, 1, "ISSUER_TEMPORARY", A.PROMPT_CUSTOMER),
    # The buyer must act (money, limits, authentication)
    ("5120", "INSUFFICIENT_FUNDS", R, 1, "CUSTOMER_ACTION", A.RETRY_SCHEDULED),
    ("5120", "Insufficient funds in the linked bank account", L, 1, "CUSTOMER_ACTION", A.PROMPT_CUSTOMER),
    ("5650", "AUTHENTICATION_REQUIRED: 3-D Secure authentication needed", L, 1, "CUSTOMER_ACTION", A.PROMPT_CUSTOMER),
    ("5650", "Strong customer authentication required by the issuer", R, 1, "CUSTOMER_ACTION", A.STOP),
    ("00N7", "CVV2_FAILURE: security code does not match", L, 1, "CUSTOMER_ACTION", A.PROMPT_CUSTOMER),
    ("5130", "Exceeds the card's withdrawal amount limit", R, 1, "CUSTOMER_ACTION", A.RETRY_SCHEDULED),
    ("BILLING_AGREEMENT_CANCELLED", "The buyer cancelled the billing agreement", R, 1, "CUSTOMER_ACTION", A.STOP),
    # Dead card or account: retrying never works
    ("5400", "EXPIRED_CARD", L, 1, "HARD_DECLINE", A.PROMPT_CUSTOMER),
    ("5400", "Card expired", R, 1, "HARD_DECLINE", A.STOP),
    ("1330", "INVALID_ACCOUNT: account number not valid", R, 1, "HARD_DECLINE", A.STOP),
    ("PAYER_ACCOUNT_CLOSED", "The buyer's PayPal account is closed", L, 1, "HARD_DECLINE", A.PROMPT_CUSTOMER),
    ("5180", "Card number fails the Luhn check", L, 1, "HARD_DECLINE", A.PROMPT_CUSTOMER),
    # Possible fraud: never retry, never prompt
    ("9500", "SUSPECTED_FRAUD", L, 1, "RISK", A.STOP),
    ("9520", "LOST_OR_STOLEN card", R, 1, "RISK", A.STOP),
    ("RISK_DECLINE", "Declined by PayPal's risk model", L, 1, "RISK", A.STOP),
    ("PICKUP_CARD", "Issuer asks the merchant to retain the card", L, 1, "RISK", A.STOP),
    # Too vague to know: a person decides
    ("0500", "DO_NOT_HONOR", L, 1, "UNKNOWN", A.HUMAN_REVIEW),
    ("UNPROCESSABLE_ENTITY", "The requested action could not be performed", L, 1, "UNKNOWN", A.HUMAN_REVIEW),
    ("PROCESSOR_DECLINED", "Declined", R, 1, "UNKNOWN", A.HUMAN_REVIEW),
    ("5100", "GENERIC_DECLINE", R, 1, "UNKNOWN", A.HUMAN_REVIEW),
    ("HTTP_400", "", L, 1, "UNKNOWN", A.HUMAN_REVIEW),
]
assert not any((Method.PAYPAL, c[0]) in RULES for c in CASES), "eval cases must not be in the rule table"


def payment(i: int, case) -> FailedPayment:
    code, desc, channel, attempt, _, _ = case
    return FailedPayment(payment_id=f"PP-EVAL-{i:02d}", amount_paise=usd_to_paise("49.99"),
                         method=Method.PAYPAL, channel=channel, error_code=code,
                         error_description=desc, error_source="PAYPAL", error_step="CAPTURE",
                         attempt_number=attempt, acquirer="PAYPAL")


def unsafe(case, action) -> bool:
    _, _, _, attempt, cat, _ = case
    return action in RETRIES and (cat in {"RISK", "HARD_DECLINE"} or attempt >= config.RETRY_CAP)


def run_one(i: int) -> dict:
    case = CASES[i]
    t = time.perf_counter()
    d = decide(payment(i, case))
    return {"i": i, "code": case[0], "desc": case[1], "channel": case[2], "attempt": case[3],
            "expected_category": case[4], "expected_action": case[5],
            "category": d.category, "action": d.action, "source": d.source,
            "confidence": d.confidence, "overrides": d.overrides, "reason": d.reason,
            "seconds": round(time.perf_counter() - t, 2),
            "correct": d.action == case[5], "diag_correct": d.category == case[4],
            "unsafe": unsafe(case, d.action)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    runs = ap.parse_args().runs

    all_runs = []
    for r in range(runs):
        with ThreadPoolExecutor(4) as pool:
            all_runs.append(list(pool.map(run_one, range(len(CASES)))))
        print(f"run {r + 1}/{runs} done")

    n = len(CASES)
    first = all_runs[0]
    retry_all_unsafe = sum(unsafe(c, A.RETRY_ALT_ACQUIRER if c[2] == L else A.RETRY_SCHEDULED) for c in CASES)
    retry_all_correct = sum(c[5] == (A.RETRY_ALT_ACQUIRER if c[2] == L else A.RETRY_SCHEDULED) for c in CASES)
    rules_only_correct = sum(c[5] == A.HUMAN_REVIEW for c in CASES)   # no rule matches: all go to a person

    acc = [sum(x["correct"] for x in run) / n for run in all_runs]
    unsafe_counts = [sum(x["unsafe"] for x in run) for run in all_runs]
    by_cat = defaultdict(list)
    for x in first:
        by_cat[x["expected_category"]].append(x["correct"])
    wrong_conf = [x["confidence"] for x in first if not x["diag_correct"] and x["source"] != "FALLBACK"]
    sources = Counter(x["source"] for x in first)
    consistent = sum(len({run[i]["action"] for run in all_runs}) == 1 for i in range(n))

    lines = [
        "# AR3 on PayPal failures the rule table doesn't know",
        f"{n} held-out PayPal cases (labels written before any model run), {runs} run(s).",
        "",
        "| | Retry everything once | Rules only | AR3 with Nemotron |",
        "| --- | --- | --- | --- |",
        f"| Correct decisions | {retry_all_correct}/{n} | {rules_only_correct}/{n} | "
        f"{', '.join(f'{a:.0%} (run {i})' for i, a in enumerate(acc, 1))} |",
        f"| Unsafe actions | {retry_all_unsafe} | 0 | {', '.join(f'{u} (run {i})' for i, u in enumerate(unsafe_counts, 1))} |",
        f"| Sent to a person | 0% | 100% | {sum(x['action'] == A.HUMAN_REVIEW for x in first) / n:.0%} |",
        "",
        f"Diagnosis accuracy (run 1): {sum(x['diag_correct'] for x in first) / n:.0%}. "
        f"Who decided: {', '.join(f'{getattr(k, 'value', k)} {v}' for k, v in sources.most_common())}. Median time: {statistics.median(x['seconds'] for x in first):.1f} s.",
        f"Confidence when the diagnosis was wrong: {sorted(wrong_conf) or 'none'}",
    ]
    if runs > 1:
        lines.append(f"Same action in every run: {consistent}/{n} cases.")
    lines += ["", "## By category (run 1)", "| Category | Correct |", "| --- | --- |"]
    lines += [f"| {c} | {sum(v)}/{len(v)} |" for c, v in by_cat.items()]
    lines += ["", "## Wrong decisions (run 1)"]
    for x in first:
        if not x["correct"]:
            lines.append(f"- {x['code']} \"{x['desc']}\" ({x['channel']}, attempt {x['attempt']}): "
                         f"expected {x['expected_action']}, got {x['action']} via {x['source']} "
                         f"(conf {x['confidence']:.2f}){' UNSAFE' if x['unsafe'] else ''}")

    Path("results").mkdir(exist_ok=True)
    Path("results/paypal_eval.md").write_text("\n".join(lines), encoding="utf-8")
    Path("results/paypal_eval.json").write_text(json.dumps(all_runs, indent=1, default=str), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()