"""Live check: real Nemotron calls (costs a few tokens). Not part of the test suite."""

import logging
import time

import config
import llm
from schemas import FailedPayment

logging.basicConfig(level=logging.WARNING)   # show warnings from llm.py

PAYMENTS = [
    FailedPayment(payment_id="live_1", amount_paise=49900, method="UPI", channel="RECURRING",
                  error_code="U30", error_description="debit failed"),
    FailedPayment(payment_id="live_2", amount_paise=129900, method="CARD", channel="LIVE_CHECKOUT",
                  error_code="PG_TIMEOUT", error_description="Acquirer did not respond in time"),
]

print("1. Is Ultra reachable?")
raw = llm.ask_nemotron(config.ULTRA_MODEL, llm.describe(PAYMENTS[0]), config.ULTRA_THINKING)
print("   ", llm.parse_reply(raw))

print("\n2. Full two-tier diagnosis:")
for p in PAYMENTS:
    start = time.perf_counter()
    d = llm.diagnose(p)
    print(f"   {p.error_code}: {d.source} | {d.category} | {d.action} | "
          f"conf={d.confidence} | {time.perf_counter() - start:.1f}s")
    print(f"      {d.reason}")