"""PayPal sandbox client for AR3: log in, create an order, capture it, and read PayPal's errors.

Only the sandbox is used (no real money). Keys come from .env:
PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET.
"""

import json
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api-m.sandbox.paypal.com"  # sandbox only, never live
TIMEOUT_S = 30

_token = {"value": None, "expires_at": 0.0}  # cached access token


class PayPalError(Exception):
    """A failed PayPal call, with the fields AR3 needs to diagnose it."""

    def __init__(self, status, name, issue, description, debug_id, raw):
        self.status = status            # HTTP status, e.g. 422
        self.name = name                # e.g. "UNPROCESSABLE_ENTITY"
        self.issue = issue              # e.g. "INSTRUMENT_DECLINED" (AR3's error code)
        self.description = description  # PayPal's message text
        self.debug_id = debug_id        # quote this to PayPal support
        self.raw = raw                  # full response body, for the demo
        super().__init__(f"{status} {name}: {issue or '-'} {description}".strip())

    @classmethod
    def from_response(cls, r: httpx.Response) -> "PayPalError":
        try:
            body = r.json()
        except ValueError:
            body = {}
        detail = (body.get("details") or [{}])[0]
        return cls(
            status=r.status_code,
            name=body.get("name", "HTTP_ERROR"),
            issue=detail.get("issue") or body.get("name") or f"HTTP_{r.status_code}",
            description=detail.get("description") or body.get("message", ""),
            debug_id=body.get("debug_id"),
            raw=body,
        )


def get_token() -> str:
    """OAuth 2.0 client-credentials login. Reuses the token until 60 s before it expires."""
    if _token["value"] and time.time() < _token["expires_at"] - 60:
        return _token["value"]
    client_id = os.getenv("PAYPAL_CLIENT_ID")
    secret = os.getenv("PAYPAL_CLIENT_SECRET")
    if not client_id or not secret:
        raise RuntimeError("PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET missing from .env")
    r = httpx.post(
        f"{BASE_URL}/v1/oauth2/token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials"},
        timeout=TIMEOUT_S,
    )
    if r.status_code >= 400:
        raise PayPalError.from_response(r)
    data = r.json()
    _token["value"] = data["access_token"]
    _token["expires_at"] = time.time() + data.get("expires_in", 300)
    return _token["value"]


def _call(method: str, path: str, *, body=None, request_id=None, mock_error=None) -> dict:
    """One PayPal API call. request_id makes retries safe; mock_error forces a sandbox error."""
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",  # full order details in the reply
    }
    if request_id:
        headers["PayPal-Request-Id"] = request_id  # same id = PayPal won't do it twice
    if mock_error:
        headers["PayPal-Mock-Response"] = json.dumps({"mock_application_codes": mock_error})
    r = httpx.request(method, f"{BASE_URL}{path}", headers=headers, json=body, timeout=TIMEOUT_S)
    if r.status_code >= 400:
        raise PayPalError.from_response(r)
    return r.json() if r.content else {}


def return_url() -> str:
    """Where PayPal sends the buyer after approving: RETURN_URL, else this Render site, else local."""
    return os.getenv("RETURN_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8501"


def create_order(amount_usd: str, reference_id: str, request_id: str | None = None) -> dict:
    """Create a checkout order the buyer must approve. amount_usd is a string like "49.99"."""
    body = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": reference_id,
            "amount": {"currency_code": "USD", "value": amount_usd},
        }],
        # Pay Now makes PayPal show a final "Pay Now" button and then send the
        # buyer back to us, instead of looping on the review page.
        "application_context": {
            "user_action": "PAY_NOW",
            "return_url": return_url(),
            "cancel_url": return_url(),
        },
    }
    return _call("POST", "/v2/checkout/orders", body=body, request_id=request_id)

def capture_order(order_id: str, request_id: str | None = None, mock_error: str | None = None) -> dict:
    """Take the money for an approved order. Raises PayPalError if PayPal refuses."""
    return _call("POST", f"/v2/checkout/orders/{order_id}/capture",
                 request_id=request_id, mock_error=mock_error)


def get_order(order_id: str) -> dict:
    """Current state of an order (CREATED, APPROVED, COMPLETED, ...)."""
    return _call("GET", f"/v2/checkout/orders/{order_id}")


def approve_link(order: dict) -> str | None:
    """The PayPal page where the buyer approves (or picks another funding source)."""
    for link in order.get("links", []):
        if link.get("rel") in ("approve", "payer-action"):
            return link["href"]
    return None
