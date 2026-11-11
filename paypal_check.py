"""Live sandbox check for paypal_client.py. Run: python paypal_check.py

1. logs in, 2. creates a $49.99 order, 3. forces two real PayPal errors on capture,
4. prints the approval link for the US test buyer.
"""

import paypal_client as pp

print("1. Login:", "ok" if pp.get_token() else "failed")

order = pp.create_order("49.99", reference_id="ar3-check-1", request_id="ar3-check-1:create")
print("2. Order:", order["id"], order["status"])

for code in ("INSTRUMENT_DECLINED", "TRANSACTION_REFUSED"):
    try:
        pp.capture_order(order["id"], mock_error=code)
        print(f"3. {code}: no error (unexpected)")
    except pp.PayPalError as e:
        print(f"3. {code}: status={e.status} issue={e.issue} debug_id={e.debug_id}")
        print("   message:", e.description[:120])

print("4. Buyer approval link:", pp.approve_link(order))