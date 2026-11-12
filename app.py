"""AR3 demo: decide one failed payment, run a batch, and see the evaluation.

Run locally:  streamlit run app.py
"""
import datetime as dt
import html
import io
import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import streamlit as st
from pydantic import ValidationError
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

# The API key: Streamlit Cloud secrets first; locally, llm.py loads it from .env
try:
    if "NEBIUS_API_KEY" in st.secrets:
        os.environ["NEBIUS_API_KEY"] = st.secrets["NEBIUS_API_KEY"]
    if "PAYPAL_CLIENT_ID" in st.secrets:
        os.environ["PAYPAL_CLIENT_ID"] = st.secrets["PAYPAL_CLIENT_ID"]
    if "PAYPAL_CLIENT_SECRET" in st.secrets:
        os.environ["PAYPAL_CLIENT_SECRET"] = st.secrets["PAYPAL_CLIENT_SECRET"]
except Exception:
    pass  # no secrets file locally, that's fine

import actions  # noqa: E402
import config  # noqa: E402  (imported after the key is set)
import paypal_client as pp  # noqa: E402
from engine import decide  # noqa: E402
from paypal_adapter import from_paypal_error  # noqa: E402
from rules import apply_rules  # noqa: E402
from schemas import Action, Channel, Decision, FailedPayment, Method  # noqa: E402

DAILY_LLM_CAP = 100      # protects the credits on the public demo
MAX_BATCH_ROWS = 50
REPO_URL = "https://github.com/punar4/ar3"

st.set_page_config(page_title="AR3 · failed payment decisions", page_icon="assets/favicon.png",
                   layout="centered",
                   initial_sidebar_state="collapsed")

# PayPal sends the buyer back here after they approve (?token=<order id>&PayerID=...)
_qp = st.query_params
if "token" in _qp and "PayerID" in _qp:
    st.markdown("### Payment approved")
    st.write(f"PayPal order {_qp['token']} is approved. You can close this tab and go back to AR3.")
    st.stop()

# ---------- Styles ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
#MainMenu, footer, [data-testid="stHeaderActionElements"] {display: none;}
html, body, .stApp, .stApp p, .stApp label, .stApp button, .stApp input, .stApp textarea,
[data-testid="stMarkdownContainer"], .stApp [data-baseweb="select"] {
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;}
.stApp {background: #f4f3ee;}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] .ar3-step) {
    background: #ffffff; border: 1px solid #e3e1d8 !important; border-radius: 14px !important;
    box-shadow: 0 1px 2px rgba(27,27,24,0.04), 0 4px 16px rgba(27,27,24,0.04); padding: 6px 8px;}
.stButton > button, .stDownloadButton > button, .stLinkButton > a {
    border-radius: 10px; font-weight: 500; border: 1px solid #cfccc1; padding: 0.45rem 1rem;}
.stButton > button[kind="primary"] {background: #1f5f46; border-color: #1f5f46; color: #fff;}
.stButton > button[kind="primary"]:hover {background: #174a36; border-color: #174a36; color: #fff;}
.stTabs [data-baseweb="tab-list"] {gap: 6px; border-bottom: 1px solid #dcdad2;}
.stTabs [data-baseweb="tab"] {font-weight: 500; padding: 8px 14px; border-radius: 8px 8px 0 0;}
.stTabs [aria-selected="true"] {color: #1f5f46 !important;}
.stTabs [data-baseweb="tab-highlight"] {background-color: #1f5f46 !important;}
[data-baseweb="input"], [data-baseweb="select"] > div {border-radius: 10px !important;}
.ar3-step {display: flex; align-items: center; gap: 12px; margin: 2px 0 8px;}
.ar3-step .num {width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center;
    justify-content: center; font-weight: 600; font-size: 0.85rem; background: #ecebe4; color: #3d3d38;}
.ar3-step .num.done {background: #1f5f46; color: #fff;}
.ar3-step .t {font-weight: 600; font-size: 1.05rem;}
.ar3-progress {display: flex; gap: 8px; margin: 0 0 14px;}
.ar3-progress .s {flex: 1; display: flex; align-items: center; gap: 8px; font-size: 0.85rem;
    color: #8f8d84; padding-top: 8px; border-top: 3px solid #dcdad2;}
.ar3-progress .s span {font-weight: 600;}
.ar3-progress .s.on {color: #1f5f46; border-top-color: #1f5f46;}
.ar3-meta {display: flex; align-items: center; gap: 10px; margin: 4px 0 10px; font-size: 0.95rem;}
.ar3-meta .pill {font-size: 0.75rem; font-weight: 600; letter-spacing: 0.04em; padding: 2px 10px;
    border-radius: 999px; background: #e7f1ec; color: #1f5f46;}
.ar3-captures {display: flex; align-items: center; gap: 14px; margin: 12px 0 4px; padding: 12px 16px;
    border-radius: 12px; background: #e7f1ec;}
.ar3-captures .n {font-size: 2rem; font-weight: 700; color: #1f5f46; line-height: 1;}
.block-container {padding-top: 2.5rem; max-width: 1040px;}
.ar3, .ar3 * {color: #1b1b18;}
.ar3 code, .ar3 .mono {font-family: 'IBM Plex Mono', monospace; font-size: 0.85em;
    background: none; padding: 0; color: #3d3d38;}
.ar3-head {display: flex; align-items: baseline; gap: 14px; margin-bottom: 4px;}
.ar3-name {font-size: 1.6rem; font-weight: 600; letter-spacing: -0.01em;}
.ar3-sub {color: #6b6b63; font-size: 0.95rem;}
.ar3-lede {font-size: 1rem; line-height: 1.55; max-width: 64ch; margin: 6px 0 18px;}
.ar3-result {border-top: 2px solid #1b1b18; padding-top: 14px; margin-top: 8px;}
.ar3-kicker {font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; color: #6b6b63;}
.ar3-action {font-size: 1.5rem; font-weight: 600; margin: 2px 0 6px;}
.ar3-action .when {font-weight: 400; color: #6b6b63; font-size: 1.1rem;}
.ar3-why {line-height: 1.55; margin: 0 0 14px; max-width: 70ch;}
.ar3-facts {display: grid; grid-template-columns: max-content 1fr; gap: 4px 18px;
    margin: 0 0 16px; font-size: 0.92rem;}
.ar3-facts dt {color: #6b6b63;}
.ar3-facts dd {margin: 0;}
.ar3-trail {list-style: none; padding: 0 0 0 4px; margin: 0; font-size: 0.92rem;}
.ar3-trail li {position: relative; padding: 4px 0 10px 22px; border-left: 1px solid #c9c7bd;}
.ar3-trail li:last-child {border-left-color: transparent;}
.ar3-trail li::before {content: ""; position: absolute; left: -5px; top: 8px; width: 9px; height: 9px;
    border-radius: 50%; background: #f7f6f2; border: 1px solid #8f8d84;}
.ar3-trail li.hit::before {background: #1f5f46; border-color: #1f5f46;}
.ar3-tone {display: inline-block; width: 10px; height: 10px; border-radius: 2px;
    margin-right: 10px; vertical-align: 0.15em;}
.tone-go {background: #1f5f46;} .tone-stop {background: #9b2c1d;} .tone-person {background: #b07a12;}
[data-testid="stMarkdownContainer"] table {border-collapse: collapse; font-size: 0.88rem; margin: 6px 0 18px;}
[data-testid="stMarkdownContainer"] th {text-align: left; font-weight: 600; border-bottom: 1.5px solid #1b1b18;
    padding: 6px 14px 6px 0; background: none;}
[data-testid="stMarkdownContainer"] td {border: none; border-bottom: 1px solid #e2e0d8; padding: 6px 14px 6px 0;}
[data-testid="stMarkdownContainer"] h2 {font-size: 1.15rem; font-weight: 600; margin-top: 18px;}
.ar3-trail .step {display: inline-block; min-width: 8.5rem; color: #6b6b63;}
.ar3-trail .changed {color: #1f5f46; font-weight: 500;}
.ar3-note {font-size: 0.9rem; color: #8a3b12; margin-top: 10px;}
.ar3-summary {font-size: 0.95rem; margin: 8px 0 12px; line-height: 1.7;}
.ar3-summary b {font-weight: 600;}
.ar3-stats {display: flex; flex-wrap: wrap; gap: 8px 40px; margin: 0 0 22px;}
.ar3-stats .n {font-size: 1.7rem; font-weight: 600; line-height: 1.1;}
.ar3-stats .l {font-size: 0.85rem; color: #6b6b63; max-width: 26ch; line-height: 1.4;}
.ar3-table-wrap {max-height: 560px; overflow: auto; border: 1px solid #dcdad2; border-radius: 4px;}
.ar3-table {border-collapse: collapse; width: 100%; font-size: 0.86rem; table-layout: fixed;}
.ar3-table th {position: sticky; top: 0; background: #eeece5; text-align: left; font-weight: 600;
    padding: 8px 12px; border-bottom: 1px solid #c9c7bd; white-space: nowrap;}
.ar3-table td {padding: 8px 12px; border-bottom: 1px solid #e6e4dc; vertical-align: top; line-height: 1.45;}
.ar3-table td {overflow-wrap: anywhere;}
.ar3-table th:nth-child(1) {width: 9%;} .ar3-table th:nth-child(2) {width: 10%;}
.ar3-table th:nth-child(3) {width: 11%;} .ar3-table th:nth-child(4) {width: 16%;}
.ar3-table th:nth-child(5) {width: 12%;} .ar3-table th.m {width: 8%;}
.ar3-tnote {color: #1f5f46; font-size: 0.8rem; margin-top: 3px;}
.ar3-foot {margin-top: 48px; padding-top: 10px; border-top: 1px solid #dcdad2;
    font-size: 0.8rem; color: #6b6b63;}
.ar3-foot a {color: #6b6b63;}
</style>
""", unsafe_allow_html=True)

ACTION_TEXT = {
    "RETRY_ALT_ACQUIRER": "Retry now through another acquirer",
    "RETRY_SCHEDULED": "Retry later",
    "PROMPT_CUSTOMER": "Ask the customer to try again",
    "STOP": "Stop. Don't retry",
    "HUMAN_REVIEW": "Send to a person",
}
CATEGORY_TEXT = {
    "GATEWAY_TEMPORARY": "Gateway or acquirer glitch",
    "ISSUER_TEMPORARY": "Customer's bank is temporarily down",
    "CUSTOMER_ACTION": "Customer can fix it",
    "HARD_DECLINE": "This card or account won't work",
    "RISK": "Possible fraud or risk",
    "UNKNOWN": "Too vague to tell",
}
SOURCE_TEXT = {
    "RULE": "Rule table",
    "LLM_FAST": "Nemotron Nano",
    "LLM_ULTRA": "Nemotron Ultra",
    "FALLBACK": "No confident answer",
}
TONE = {"RETRY_ALT_ACQUIRER": "tone-go", "RETRY_SCHEDULED": "tone-go", "PROMPT_CUSTOMER": "tone-go",
        "STOP": "tone-stop", "HUMAN_REVIEW": "tone-person"}
SAFE_NEXT_STEP = {"RETRY_ALT_ACQUIRER", "RETRY_SCHEDULED", "PROMPT_CUSTOMER"}

PRESETS = {
    "UPI AutoPay, bank down (BANK_503)": dict(
        method="UPI", channel="RECURRING", error_code="BANK_503",
        error_description="Remitter bank CBS not available", amount_paise=49900, attempt_number=1),
    "Card checkout, gateway error (PG_E102)": dict(
        method="CARD", channel="LIVE_CHECKOUT", error_code="PG_E102",
        error_description="Payment gateway internal error, please retry", amount_paise=129900,
        attempt_number=1),
    "UPI, 'debit failed' with no reason (U30)": dict(
        method="UPI", channel="LIVE_CHECKOUT", error_code="U30", error_description="debit failed",
        amount_paise=19900, attempt_number=1),
    "Card, suspected fraud (59)": dict(
        method="CARD", channel="LIVE_CHECKOUT", error_code="59", error_description="Suspected fraud",
        amount_paise=6_000_000, attempt_number=1),
    "Card renewal, low balance, 3rd attempt (51)": dict(
        method="CARD", channel="RECURRING", error_code="51", error_description="Insufficient funds",
        amount_paise=49900, attempt_number=3),
    "UPI AutoPay, compliance hold (AML_HOLD)": dict(
        method="UPI", channel="RECURRING", error_code="AML_HOLD",
        error_description="Transaction held for compliance review", amount_paise=129900,
        attempt_number=1),
}

TEMPLATE_ROWS = [
    dict(payment_id="pay_001", amount_paise=49900, method="UPI", channel="RECURRING",
         error_code="U30", error_description="debit failed", attempt_number=1, acquirer="ACQ_A"),
    dict(payment_id="pay_002", amount_paise=129900, method="CARD", channel="LIVE_CHECKOUT",
         error_code="PG_E102", error_description="Payment gateway internal error", attempt_number=1,
         acquirer="ACQ_A"),
    dict(payment_id="pay_003", amount_paise=19900, method="CARD", channel="RECURRING",
         error_code="51", error_description="Insufficient funds", attempt_number=2, acquirer="ACQ_B"),
]


# ---------- Daily cap on model calls (shared by all visitors of this app) ----------
@st.cache_resource
def llm_counter() -> dict:
    return {"day": dt.date.today(), "calls": 0}


def llm_allowed() -> bool:
    c = llm_counter()
    if c["day"] != dt.date.today():
        c["day"], c["calls"] = dt.date.today(), 0
    return c["calls"] < DAILY_LLM_CAP


# ---------- Deciding ----------
@st.cache_data(show_spinner=False)
def decide_cached(payment_json: str, use_llm: bool) -> dict:
    """Same payment twice = no second model call."""
    payment = FailedPayment.model_validate_json(payment_json)
    start = time.perf_counter()
    decision = decide(payment, use_llm=use_llm).model_dump(mode="json")
    decision["seconds"] = round(time.perf_counter() - start, 2)
    return decision


def run(payment: FailedPayment) -> tuple[dict, bool]:
    """Returns (decision, capped). The model is used only when no rule matches and the cap allows."""
    needs_llm = apply_rules(payment) is None
    use_llm = needs_llm and llm_allowed()
    decision = decide_cached(payment.model_dump_json(), use_llm)
    if use_llm:
        llm_counter()["calls"] += 1
    return decision, needs_llm and not use_llm


# ---------- Formatting ----------
def rupees(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"


def wait_text(minutes: int | None) -> str:
    if not minutes:
        return ""
    if minutes % 1440 == 0:
        days = minutes // 1440
        return f"in {days} day{'s' if days > 1 else ''}"
    if minutes % 60 == 0:
        return f"in {minutes // 60} h"
    return f"in {minutes} min"


def split_reason(reason: str) -> tuple[str, list[str]]:
    """'LLM_FAST: why | Safety check 'x': note' -> ('why', ['x: note'])."""
    main, *notes = reason.split(" | ")
    main = re.sub(r"^(LLM_FAST|LLM_ULTRA|FALLBACK)\s*:\s*", "", main)
    notes = [re.sub(r"^Safety check '([^']+)':\s*", r"\1: ", n) for n in notes]
    return main, notes


def short_reason(reason: str) -> str:
    """'Rule: CARD 14 = Invalid card number, so STOP for RECURRING' -> 'Invalid card number'."""
    m = re.match(r"^Rule: \S+ \S+ = (.+?), so ", reason)
    return m.group(1) if m else reason


def trail(d: dict, payment: FailedPayment, capped: bool) -> list[tuple[str, str, bool]]:
    """The path the payment took, as (step, what happened, changed the decision?)."""
    code = html.escape(payment.error_code)
    nano, ultra = "Nemotron Nano", "Nemotron Ultra"
    steps = []
    if d["source"] == "RULE":
        steps.append(("Rule table", f"matched {payment.method.value} <code>{code}</code>", True))
    else:
        steps.append(("Rule table", f"no rule for <code>{code}</code>", False))
        if capped:
            steps.append(("Nemotron", "skipped: today's demo limit is used up", False))
        elif d["source"] == "LLM_FAST":
            steps.append((nano,
                          f"<code>{d['category']}</code>, confidence {d['confidence']:.2f}", True))
            if "two independent reads agreed" in d["reason"]:
                steps.append((f"{nano} (2nd read)", "reasoning on: same cause, so it's trusted", False))
        elif d["source"] == "LLM_ULTRA":
            if "broke a tie" in d["reason"]:
                steps.append((nano, "two reads disagreed on the cause, escalated", False))
            else:
                steps.append((nano, "unsure or invalid, escalated", False))
            steps.append((ultra,
                          f"<code>{d['category']}</code>, confidence {d['confidence']:.2f}", True))
        else:
            if "disagreed" in d["reason"]:
                steps.append((nano, "two reads disagreed on the cause, escalated", False))
                steps.append((ultra, "didn't settle it", False))
            else:
                steps.append((nano, "unsure or invalid, escalated", False))
                steps.append((ultra, "unsure or invalid", False))
    _, notes = split_reason(d["reason"])
    if notes:
        for n in notes:
            steps.append(("Safety check", html.escape(n), True))
    else:
        steps.append(("Safety checks", "all passed, nothing changed", False))
    return steps


def show_decision(d: dict, payment: FailedPayment, capped: bool) -> None:
    why, _ = split_reason(d["reason"])
    facts = [
        ("Diagnosis", CATEGORY_TEXT.get(d["category"], d["category"])),
        ("Confidence", f"{d['confidence']:.2f}"),
        ("Decided by", SOURCE_TEXT.get(d["source"], d["source"])),
        ("Time", f"{d.get('seconds', 0):.2f} s"),
    ]
    via_paypal = d.get("next_acquirer") == "PAYPAL"
    if d.get("next_acquirer") and not via_paypal:
        facts.append(("Next acquirer", f"<span class='mono'>{html.escape(d['next_acquirer'])}</span>"))
    if d.get("idempotency_key"):
        facts.append(("PayPal-Request-Id" if via_paypal else "Idempotency key",
                      f"<span class='mono'>{html.escape(d['idempotency_key'])}</span>"))
    action_text = ("Retry now through PayPal, safely" if via_paypal
                   else ACTION_TEXT.get(d["action"], d["action"]))

    facts_html = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts)
    trail_html = "".join(
        f"<li class='{'hit' if changed else ''}'><span class='step'>{step}</span>"
        f"<span class='{'changed' if changed else ''}'>{what}</span></li>"
        for step, what, changed in trail(d, payment, capped))
    note = ("<div class='ar3-note'>Today's demo limit for model calls is used up, so this unknown "
            "code was sent to a person.</div>" if capped else "")

    st.markdown(f"""
<div class="ar3 ar3-result">
  <div class="ar3-kicker">Recommendation</div>
  <div class="ar3-action"><span class="ar3-tone {TONE.get(d['action'], 'tone-person')}"></span>{action_text}
    <span class="when">{wait_text(d.get('wait_minutes'))}</span></div>
  <p class="ar3-why">{html.escape(why)}</p>
  <dl class="ar3-facts">{facts_html}</dl>
  <div class="ar3-kicker" style="margin-bottom:6px">How it got here</div>
  <ol class="ar3-trail">{trail_html}</ol>{note}
</div>""", unsafe_allow_html=True)


# ---------- PayPal tab ----------
FAILURE_OPTIONS = {
    "Card or account declined (INSTRUMENT_DECLINED)": ("real", "INSTRUMENT_DECLINED"),
    "Buyer must act (PAYER_ACTION_REQUIRED)": ("real", "PAYER_ACTION_REQUIRED"),
    "PayPal refused it (TRANSACTION_REFUSED)": ("real", "TRANSACTION_REFUSED"),
    "Already captured (ORDER_ALREADY_CAPTURED)": ("real", "ORDER_ALREADY_CAPTURED"),
    "PayPal server error (INTERNAL_SERVER_ERROR)": ("real", "INTERNAL_SERVER_ERROR"),
    "Unclear processor decline, goes to Nemotron (simulated)":
        ("sim", "PROCESSOR_DECLINED", "Declined by processor: 0500 DO_NOT_HONOR"),
    "Bank says limit exceeded, goes to Nemotron (simulated)":
        ("sim", "5130", "Exceeds the card's withdrawal amount limit"),
    "Expired card on a subscription, goes to Nemotron (simulated)":
        ("sim", "5400", "EXPIRED_CARD"),
}
CHANNEL_HELP = ("LIVE_CHECKOUT: the customer is waiting on the payment page. "
                "RECURRING: a subscription or AutoPay debit; the customer isn't there.")


def step_head(n: int, title: str, done: bool) -> None:
    st.markdown(f"<div class='ar3-step'><span class='num {'done' if done else ''}'>{n}</span>"
                f"<span class='t'>{title}</span></div>", unsafe_allow_html=True)


def progress_bar(stage: int) -> None:
    """Create, Fail, Decide, Act: how far this order has got."""
    names = ["Create", "Fail", "Decide", "Act"]
    items = "".join(f"<div class='s {'on' if i < stage else ''}'><span>{i + 1}</span>{n}</div>"
                    for i, n in enumerate(names))
    st.markdown(f"<div class='ar3-progress'>{items}</div>", unsafe_allow_html=True)


def paypal_tab() -> None:
    st.markdown("<div class='ar3'><p class='ar3-why'>A real PayPal sandbox order, a real PayPal "
                "failure, and AR3's decision. Nothing is charged without a named person approving "
                "it.</p></div>", unsafe_allow_html=True)
    st.session_state.setdefault("pp_results", [])
    bar = st.empty()

    # Step 1: create the order
    with st.container(border=True):
        order = st.session_state.get("pp_order")
        step_head(1, "Create a sandbox order", bool(order))
        c1, c2 = st.columns([1, 1], vertical_alignment="bottom")
        amount = c1.text_input("Amount (USD)", "49.99", key="pp_amount_input")
        if c2.button("Create order", key="pp_create", type="primary", width="stretch"):
            try:
                order = pp.create_order(amount, reference_id="ar3-demo")
            except (pp.PayPalError, RuntimeError) as err:
                st.error(f"PayPal: {err}")
            else:
                st.session_state.pp_order = order
                st.session_state.pp_amount = amount
                st.session_state.pp_results = []
                for key in ("pp_error", "pp_decision", "pp_plan"):
                    st.session_state.pop(key, None)

        order = st.session_state.get("pp_order")
        if order:
            st.markdown(f"<div class='ar3-meta'>Order <span class='mono'>{html.escape(order['id'])}</span>"
                        f"<span class='pill'>{html.escape(order.get('status', ''))}</span></div>",
                        unsafe_allow_html=True)
            link = pp.approve_link(order)
            if link:
                st.link_button("Open as test buyer (optional)", link)
                st.caption("Approve it as the sandbox buyer if you want the retry at the end to "
                           "really capture the money.")

    # Step 2: make the payment fail
    e = st.session_state.get("pp_error")
    if order:
        with st.container(border=True):
            step_head(2, "Make the payment fail", bool(e))
            label = st.selectbox("Failure", list(FAILURE_OPTIONS), key="pp_failure")
            c1, c2 = st.columns([1.4, 0.6])
            channel = c1.selectbox("Channel", [c.value for c in Channel], key="pp_channel",
                                   help=CHANNEL_HELP)
            attempt = c2.number_input("Attempt", min_value=1, value=1, key="pp_attempt")
            st.caption("Real = PayPal's sandbox returns this error on purpose (negative testing). "
                       "Simulated = PayPal can't produce it on demand, so AR3 receives a PayPal-style "
                       "error to show Nemotron's part.")

            if st.button("Capture payment", key="pp_capture", type="primary"):
                choice = FAILURE_OPTIONS[label]
                e = None
                if choice[0] == "real":
                    try:
                        pp.capture_order(order["id"], mock_error=choice[1])
                    except pp.PayPalError as err:
                        e = err
                    except RuntimeError as err:
                        st.error(f"PayPal: {err}")
                else:
                    e = pp.PayPalError(422, "UNPROCESSABLE_ENTITY", choice[1], choice[2], None,
                                       {"simulated": True, "issue": choice[1],
                                        "description": choice[2]})
                if e is not None:
                    st.session_state.pp_error = e
                    st.session_state.pp_channel_used = channel
                    st.session_state.pp_attempt_used = attempt
                    st.session_state.pp_results = []
                    for key in ("pp_decision", "pp_plan"):
                        st.session_state.pop(key, None)

            e = st.session_state.get("pp_error")
            if e:
                st.error(f"PayPal said {e.status}: {e.issue}")
                with st.expander("PayPal's response"):
                    st.json(e.raw)

    # Step 3: AR3 decides
    if order and e:
        with st.container(border=True):
            step_head(3, "AR3 decides", True)
            payment = from_paypal_error(e, order["id"], st.session_state.get("pp_amount", amount),
                                        channel=Channel(st.session_state.get("pp_channel_used",
                                                                            Channel.LIVE_CHECKOUT.value)),
                                        attempt_number=st.session_state.get("pp_attempt_used", 1))
            if "pp_decision" not in st.session_state:      # decide once per failure, not on every rerun
                st.session_state.pp_decision, st.session_state.pp_capped = run(payment)
            decision = st.session_state.pp_decision
            show_decision(decision, payment, st.session_state.pp_capped)
            d = Decision.model_validate({k: v for k, v in decision.items() if k != "seconds"})
            st.session_state.pp_plan = actions.plan(d, order)

    # Step 4: approve and act
    p = st.session_state.get("pp_plan") if (order and e) else None
    if p:
        with st.container(border=True):
            step_head(4, "Approve and act", bool(st.session_state.pp_results))
            st.markdown(f"**{html.escape(p.title)}**")
            if p.paypal_call:
                st.code(p.paypal_call)
            else:
                st.caption("No PayPal call: AR3 never retries this kind of failure.")
            if p.request_id:
                st.markdown(f"PayPal-Request-Id: <span class='mono'>{html.escape(p.request_id)}</span>",
                            unsafe_allow_html=True)
            if p.customer_link:
                st.link_button("Link for the buyer", p.customer_link)
            if p.run_at:
                st.markdown(f"Runs at <span class='mono'>{html.escape(p.run_at)}</span>",
                            unsafe_allow_html=True)

            who = st.text_input("Approved by", placeholder="your name", key="pp_who")
            # Buttons stay enabled: a disabled button only wakes up after the text box loses focus,
            # which looks broken. The name is checked on click instead (execute() checks it too).
            b1, b2 = st.columns([1, 1])
            if b1.button("Approve and run", key="pp_approve", type="primary", width="stretch"):
                if who.strip():
                    st.session_state.pp_results.append(actions.execute(p, order["id"], approved_by=who))
                else:
                    st.warning("Type the approver's name first. AR3 never acts without one.")
            if p.action == Action.RETRY_ALT_ACQUIRER and st.session_state.pp_results:
                if b2.button("Send the same retry again", key="pp_again", width="stretch") \
                        and who.strip():
                    st.session_state.pp_results.append(actions.execute(p, order["id"], approved_by=who))

            for r in st.session_state.pp_results:
                (st.success if r.ok else st.warning)(f"{r.summary} · approved by {r.approved_by} at {r.at}")
                if r.paypal_response:
                    with st.expander("PayPal's response"):
                        st.json(r.paypal_response)

            if st.session_state.pp_results:
                try:
                    fresh = pp.get_order(order["id"])
                except (pp.PayPalError, RuntimeError) as err:
                    st.error(f"PayPal: {err}")
                else:
                    captures = sum(len(u.get("payments", {}).get("captures", []))
                                   for u in fresh.get("purchase_units", []))
                    st.markdown(f"<div class='ar3-captures'><span class='n'>{captures}</span>"
                                f"<span>capture{'s' if captures != 1 else ''} on this order. Same "
                                f"PayPal-Request-Id, so PayPal never charges twice.</span></div>",
                                unsafe_allow_html=True)

    stage = 4 if st.session_state.pp_results else 3 if p else 2 if (order and e) else 1 if order else 0
    with bar:
        progress_bar(stage)


# ---------- Batch queue ----------
QUEUE_STATUS = ["New", "Approved", "Done", "Rejected"]
ROW_STYLE = """
function(params) {
  var a = params.data.action;
  if (a === 'STOP') { return {'background-color': '#fdecec'}; }
  if (a === 'HUMAN_REVIEW') { return {'background-color': '#fff6e0'}; }
  return {'background-color': '#eaf7ee'};
}
"""


def html_table(view: pd.DataFrame) -> None:
    """The plain HTML table the Batch tab used before the grid. Kept, but no longer called."""
    cols = [("payment_id", "Payment"), ("amount", "Amount"), ("error_code", "Code"),
            ("action", "Recommendation"), ("decided_by", "Decided by")]
    if "correct" in view:
        cols.append(("correct", "Correct"))
    head = "".join(f"<th class='{'m' if key == 'correct' else ''}'>{label}</th>"
                   for key, label in cols) + "<th>Reason</th>"
    body = []
    for _, r in view.iterrows():
        cells = []
        for key, _ in cols:
            val = r[key]
            if key == "correct":
                val = "yes" if val else "no"
            cells.append(f"<td>{html.escape(str(val))}</td>")
        main, notes = split_reason(str(r["full_reason"]))
        note_html = "".join(f"<div class='ar3-tnote'>{html.escape(n)}</div>" for n in notes)
        cells.append(f"<td>{html.escape(short_reason(main))}{note_html}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    st.markdown(f"<div class='ar3 ar3-table-wrap'><table class='ar3-table'><thead><tr>{head}</tr></thead>"
                f"<tbody>{''.join(body)}</tbody></table></div>", unsafe_allow_html=True)


def queue_grid(view: pd.DataFrame, raw_action: pd.Series) -> None:
    """AR3's recovery queue: one row per payment, colour-coded, with an editable Status."""
    saved = st.session_state.get("batch_status", {})
    queue = pd.DataFrame({
        "Payment": view["payment_id"],
        "Error": view["error_code"],
        "Recommendation": view["action"],
        "Reason": view["reason"],
        "Amount (₹)": view["amount"],
        "Method": view["method"],
        "Channel": view["channel"].map({"LIVE_CHECKOUT": "Checkout", "RECURRING": "Recurring"})
                                  .fillna(view["channel"]),
        "Decided by": view["decided_by"],
        "Confidence": view["confidence"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "—"),
        "action": raw_action.values,   # hidden; only the row colour reads it
    })
    queue["Status"] = [saved.get(pid, "New") for pid in queue["Payment"]]
    builder = GridOptionsBuilder.from_dataframe(queue)
    builder.configure_default_column(sortable=True, filter=True, resizable=True)
    builder.configure_column("action", hide=True)
    for col, width in [("Payment", 100), ("Amount (₹)", 120), ("Method", 95), ("Channel", 115),
                       ("Error", 110), ("Decided by", 130), ("Confidence", 105), ("Status", 115)]:
        builder.configure_column(col, width=width, minWidth=width)
    builder.configure_column("Recommendation", minWidth=190, flex=1, pinned="left",
                             wrapText=True, autoHeight=True)
    builder.configure_column("Reason", minWidth=260, flex=2, wrapText=True, autoHeight=True)
    builder.configure_column("Status", editable=True, cellEditor="agSelectCellEditor",
                             cellEditorParams={"values": QUEUE_STATUS}, pinned="right")
    builder.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)
    options = builder.build()
    options["getRowStyle"] = JsCode(ROW_STYLE)
    grid = AgGrid(queue, gridOptions=options, theme="alpine", height=560,
                  allow_unsafe_jscode=True, update_on=["cellValueChanged"], key="batch_grid")
    data = pd.DataFrame(grid["data"]) if grid.get("data") is not None else queue
    st.session_state.batch_status = dict(zip(data["Payment"], data["Status"]))
    st.caption("Green: a safe next step. Red: stopped. Amber: sent to a person. "
               "Click a Status cell to mark a row Approved, Done or Rejected.")
    st.download_button("Download decisions (CSV)", data.drop(columns=["action"], errors="ignore").to_csv(index=False),
                       "ar3_decisions.csv", "text/csv")


# ---------- Page ----------
st.markdown("""
<div class="ar3">
  <div class="ar3-head"><span class="ar3-name">AR3</span>
    <span class="ar3-sub">a decision layer for failed UPI, card and PayPal payments</span></div>
  <p class="ar3-lede">Give it a failed payment. It says whether to retry, ask the customer, stop,
  or hand it to a person, and why. Known error codes go to a rule table. Unclear ones go to
  NVIDIA Nemotron on Nebius Token Factory. Every answer then passes safety checks that can
  overrule it. For PayPal, AR3 can also act through PayPal's sandbox, but only after a person approves.</p>
  <div class="ar3-stats">
    <div><div class="n">94&ndash;97%</div><div class="l">right decisions on 31 held-out PayPal failures no rule covers (rules alone: 5 of 31)</div></div>
    <div><div class="n">99%</div><div class="l">right decisions on 150 UPI and card test payments (rules alone: 31%)</div></div>
    <div><div class="n">0</div><div class="l">unsafe retries in every run (retrying everything: 11 PayPal, 50 UPI/card)</div></div>
  </div>
</div>""", unsafe_allow_html=True)

tab_pp, tab_one, tab_batch, tab_eval = st.tabs(["PayPal (live sandbox)", "One payment", "Batch", "Evaluation"])

# ---------- Tab 0: PayPal (live sandbox) ----------
with tab_pp:
    paypal_tab()

# ---------- Tab 1: one payment ----------
with tab_one:
    preset_name = st.selectbox("Example", list(PRESETS))
    preset = PRESETS[preset_name]
    k = preset_name  # widget keys depend on the example, so picking one refills the fields

    c1, c2, c3 = st.columns([1, 1.3, 0.8])
    methods, channels = [m.value for m in Method], [c.value for c in Channel]
    method = c1.selectbox("Method", methods, index=methods.index(preset["method"]), key=f"m_{k}")
    channel = c2.selectbox("Channel", channels, index=channels.index(preset["channel"]), key=f"c_{k}",
                           help="LIVE_CHECKOUT: the customer is waiting on the payment page. "
                                "RECURRING: a subscription or AutoPay debit; the customer isn't there.")
    attempt = c3.number_input("Attempt", min_value=1, value=preset["attempt_number"], key=f"a_{k}")
    c4, c5, c6 = st.columns([1, 2.2, 1])
    code = c4.text_input("Error code", preset["error_code"], key=f"e_{k}")
    desc = c5.text_input("Error description", preset["error_description"], key=f"d_{k}")
    amount = c6.number_input("Amount (₹)", min_value=1.0, value=preset["amount_paise"] / 100,
                             key=f"r_{k}")

    if st.button("Decide", type="primary"):
        try:
            payment = FailedPayment(payment_id="demo_1", amount_paise=round(amount * 100), method=method,
                                    channel=channel, error_code=code, error_description=desc,
                                    attempt_number=attempt, acquirer="ACQ_A")
        except ValidationError as err:
            st.error(f"Check the fields: {err.errors()[0]['msg']}")
        else:
            with st.spinner("Deciding"):
                decision, capped = run(payment)
            show_decision(decision, payment, capped)

# ---------- Tab 2: batch ----------
with tab_batch:
    st.markdown("<div class='ar3'><p class='ar3-why'>Upload a CSV or JSON of failed payments "
                f"(up to {MAX_BATCH_ROWS} rows). Without a file, this shows AR3's decisions on its "
                "150 test payments.</p></div>", unsafe_allow_html=True)
    u1, u2 = st.columns([3, 1])
    upload = u1.file_uploader("Failed payments", type=["csv", "json"], label_visibility="collapsed")
    u2.download_button("CSV template", pd.DataFrame(TEMPLATE_ROWS).to_csv(index=False),
                       "ar3_template.csv", "text/csv")

    rows, row_errors = [], []
    if upload is not None:
        try:
            if upload.name.lower().endswith(".csv"):
                raw = pd.read_csv(io.BytesIO(upload.getvalue()), dtype=str, keep_default_na=False)
                records = raw.to_dict("records")
            else:
                records = json.loads(upload.getvalue())
                records = records if isinstance(records, list) else [records]
        except Exception as err:
            st.error(f"Couldn't read the file: {err}")
            records = []
        if len(records) > MAX_BATCH_ROWS:
            st.warning(f"Only the first {MAX_BATCH_ROWS} rows are used.")
            records = records[:MAX_BATCH_ROWS]

        payments = []
        for i, rec in enumerate(records, start=1):
            clean = {key: val for key, val in rec.items() if val not in ("", None)}
            clean.setdefault("payment_id", f"row_{i}")
            try:
                payments.append(FailedPayment.model_validate(clean))
            except ValidationError as err:
                first = err.errors()[0]
                row_errors.append(f"Row {i}: {'.'.join(map(str, first['loc']))}: {first['msg']}")

        progress = st.progress(0.0, text="Deciding")
        for n, p in enumerate(payments, start=1):
            d, _ = run(p)
            rows.append(dict(payment_id=p.payment_id, amount_paise=p.amount_paise, method=p.method.value,
                             channel=p.channel.value, error_code=p.error_code, action=d["action"],
                             category=d["category"], decided_by=d["source"],
                             confidence=d.get("confidence"),
                             reason=short_reason(split_reason(d["reason"])[0]), full_reason=d["reason"]))
            progress.progress(n / max(len(payments), 1), text=f"Decided {n} of {len(payments)}")
        progress.empty()
        if row_errors:
            with st.expander(f"{len(row_errors)} rows skipped"):
                st.write("\n".join(f"- {e}" for e in row_errors))
    else:
        path = Path("results/full_decisions.json")
        if path.exists():
            for c in json.loads(path.read_text(encoding="utf-8")):
                got = c.get("got", {})
                rows.append(dict(payment_id=c["payment_id"], amount_paise=c["amount_paise"],
                                 method=c["method"], channel=c["channel"], error_code=c["error_code"],
                                 action=got.get("action"), category=got.get("category"),
                                 decided_by=got.get("source"), confidence=got.get("confidence"),
                                 expected=c.get("expected_action"),
                                 correct=got.get("correct"),
                                 reason=short_reason(split_reason(got.get("reason") or "")[0]),
                                 full_reason=got.get("reason") or ""))

    if rows:
        df = pd.DataFrame(rows)
        safe = df.loc[df["action"].isin(SAFE_NEXT_STEP), "amount_paise"].sum()
        st.markdown(f"""<div class="ar3 ar3-summary">
<b>{len(df)}</b> payments, <b>{rupees(df['amount_paise'].sum())}</b> at risk.
<b>{rupees(safe)}</b> has a safe next step (retry or ask the customer).
<b>{int((df['action'] == 'STOP').sum())}</b> stopped,
<b>{int((df['action'] == 'HUMAN_REVIEW').sum())}</b> sent to a person.</div>""",
                    unsafe_allow_html=True)

        chosen = st.pills("Show", list(ACTION_TEXT), selection_mode="multi", default=list(ACTION_TEXT),
                          format_func=lambda a: ACTION_TEXT[a]) or []
        view = df[df["action"].isin(chosen)].copy()
        view.insert(1, "amount", view.pop("amount_paise").map(rupees))
        raw_action = view["action"]
        view["action"] = raw_action.map(ACTION_TEXT)
        view["decided_by"] = view["decided_by"].map(lambda s: SOURCE_TEXT.get(s, s))
        view["category"] = view["category"].map(lambda s: CATEGORY_TEXT.get(s, s))
        if "expected" in view:
            view["expected"] = view["expected"].map(lambda s: ACTION_TEXT.get(s, s))
        queue_grid(view, raw_action)

# ---------- Tab 3: evaluation ----------
with tab_eval:
    pp_eval = Path("results/paypal_eval.md")
    if pp_eval.exists():
        st.markdown(pp_eval.read_text(encoding="utf-8"))
    for label, name in [("PayPal, first held-out run (before the design changes)",
                         "paypal_eval_v1_before_fixes.md"),
                        ("PayPal, after the second read", "paypal_eval_v2_second_read.md")]:
        old = Path("results") / name
        if old.exists():
            with st.expander(f"Earlier: {label}"):
                st.markdown(old.read_text(encoding="utf-8"))
    st.markdown("---")
    eval_path = Path("results/eval.md")
    if eval_path.exists():
        st.markdown(eval_path.read_text(encoding="utf-8"))
    else:
        st.info("Run `python evaluate.py --tiers` to create results/eval.md.")
    for label, name in [("Run 1, first prompt", "eval_prompt_v1.md"),
                        ("Run 2, prompt with the action table", "eval_prompt_v2.md")]:
        old = Path("results") / name
        if old.exists():
            with st.expander(f"Earlier: {label}"):
                st.markdown(old.read_text(encoding="utf-8"))

# ---------- Footer ----------
c = llm_counter()
st.markdown(f"""
<div class="ar3 ar3-foot">
  Fast tier <span class="mono">{config.FAST_MODEL}</span>, read twice (reasoning off and on) · escalates to
  <span class="mono">{config.ULTRA_MODEL}</span> if unsure or if the two reads disagree<br>
  Model calls today on this demo: {c['calls']} of {DAILY_LLM_CAP} ·
  <a href="{REPO_URL}">Source on GitHub</a>
</div>""", unsafe_allow_html=True)