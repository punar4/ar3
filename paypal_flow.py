"""The full demo story, live in the sandbox. Run: python paypal_flow.py

1. Create a $49.99 order. 2. You approve it in the browser as the US sandbox buyer.
3. Capture fails with a forced PayPal 500. 4. AR3 decides. 5. A person approves -> AR3 retries.
6. The same retry is sent again: PayPal-Request-Id means the buyer is charged once.
"""

import actions
import paypal_client as pp
from engine import decide
from paypal_adapter import from_paypal_error

order = pp.create_order("49.99", reference_id="ar3-flow", request_id=None)
print("Order:", order["id"])
print("Open this, log in as the US sandbox buyer, click Pay/Continue, then come back:")
print("  ", pp.approve_link(order))
input("Press Enter after approving... ")
print("Status now:", pp.get_order(order["id"])["status"])

try:
    pp.capture_order(order["id"], mock_error="INTERNAL_SERVER_ERROR")
except pp.PayPalError as err:
    print("\nCapture failed:", err.status, err.issue)
    payment = from_paypal_error(err, order["id"], "49.99")

decision = decide(payment, use_llm=False)
print("AR3:", decision.action, "|", decision.reason)

p = actions.plan(decision, order)
print("Planned:", p.title, "|", p.paypal_call, "| PayPal-Request-Id:", p.request_id)

r1 = actions.execute(p, order["id"], approved_by="demo-operator")
print("\nApproved, run 1:", r1.ok, r1.summary)
r2 = actions.execute(p, order["id"], approved_by="demo-operator")
print("Same retry again:", r2.ok, r2.summary)

final = pp.get_order(order["id"])
captures = [c for u in final.get("purchase_units", [])
            for c in u.get("payments", {}).get("captures", [])]
print(f"\nFinal: {final['status']}, captures: {len(captures)} (should be 1: charged once)")
