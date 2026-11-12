"""Live sandbox check: real PayPal errors -> AR3 decisions. Run: python paypal_check.py

Creates one $49.99 order, forces each PayPal error on capture (sandbox negative testing),
and runs it through AR3 with rules only (no Nemotron calls, so no credits used).
"""

import paypal_client as pp
from engine import decide
from paypal_adapter import from_paypal_error

CODES = ["INSTRUMENT_DECLINED", "PAYER_ACTION_REQUIRED", "TRANSACTION_REFUSED",
         "ORDER_ALREADY_CAPTURED", "DUPLICATE_INVOICE_ID", "PAYER_CANNOT_PAY",
         "INTERNAL_SERVER_ERROR"]

print("Login:", "ok" if pp.get_token() else "failed")
order = pp.create_order("49.99", reference_id="ar3-check-2", request_id="ar3-check-2:create")
print("Order:", order["id"], order["status"], "| approve:", pp.approve_link(order))
print()

for code in CODES:
    try:
        pp.capture_order(order["id"], mock_error=code)
        print(f"{code:<26} PayPal returned no error (unexpected)")
        continue
    except pp.PayPalError as e:
        err = e
    d = decide(from_paypal_error(err, order["id"], "49.99"), use_llm=False)
    got = "ok " if err.issue == code else f"PayPal sent {err.issue} ({err.status})"
    print(f"{code:<26} {got} -> {d.action} ({d.source})")
