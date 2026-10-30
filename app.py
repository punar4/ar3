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

# The API key: Streamlit Cloud secrets first; locally, llm.py loads it from .env
try:
    if "NEBIUS_API_KEY" in st.secrets:
        os.environ["NEBIUS_API_KEY"] = st.secrets["NEBIUS_API_KEY"]
except Exception:
    pass  # no secrets file locally, that's fine

import config  # noqa: E402  (imported after the key is set)
from engine import decide  # noqa: E402
from rules import apply_rules  # noqa: E402
from schemas import Channel, FailedPayment, Method  # noqa: E402

DAILY_LLM_CAP = 300      # protects the credits on the public demo
MAX_BATCH_ROWS = 200
REPO_URL = "https://github.com/punar4/ar3"

st.set_page_config(page_title="AR3 · failed payment decisions", page_icon=":material/account_balance:",
                   layout="centered",
                   initial_sidebar_state="collapsed")

# ---------- Styles ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap');
#MainMenu, footer, [data-testid="stHeaderActionElements"] {display: none;}
.block-container {padding-top: 2.5rem; max-width: 880px;}
.ar3, .ar3 * {font-family: inherit; color: #1b1b18;}
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
        elif d["source"] == "LLM_ULTRA":
            steps.append((nano, "unsure or invalid, escalated", False))
            steps.append((ultra,
                          f"<code>{d['category']}</code>, confidence {d['confidence']:.2f}", True))
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
    if d.get("next_acquirer"):
        facts.append(("Next acquirer", f"<span class='mono'>{html.escape(d['next_acquirer'])}</span>"))
    if d.get("idempotency_key"):
        facts.append(("Idempotency key", f"<span class='mono'>{html.escape(d['idempotency_key'])}</span>"))

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
  <div class="ar3-action"><span class="ar3-tone {TONE.get(d['action'], 'tone-person')}"></span>{ACTION_TEXT.get(d['action'], d['action'])}
    <span class="when">{wait_text(d.get('wait_minutes'))}</span></div>
  <p class="ar3-why">{html.escape(why)}</p>
  <dl class="ar3-facts">{facts_html}</dl>
  <div class="ar3-kicker" style="margin-bottom:6px">How it got here</div>
  <ol class="ar3-trail">{trail_html}</ol>{note}
</div>""", unsafe_allow_html=True)


# ---------- Page ----------
st.markdown("""
<div class="ar3">
  <div class="ar3-head"><span class="ar3-name">AR3</span>
    <span class="ar3-sub">a decision layer for failed UPI and card payments</span></div>
  <p class="ar3-lede">Give it a failed payment. It says whether to retry, ask the customer, stop,
  or hand it to a person, and why. Known error codes go to a rule table. Unclear ones go to
  NVIDIA Nemotron on Nebius Token Factory. Every answer then passes safety checks that can
  overrule it. AR3 only recommends; it never moves money.</p>
  <div class="ar3-stats">
    <div><div class="n">98%</div><div class="l">right decisions on 150 test payments (rules alone: 31%)</div></div>
    <div><div class="n">0</div><div class="l">unsafe retries (retrying everything: 50)</div></div>
    <div><div class="n">11%</div><div class="l">sent to a person when the error was too vague</div></div>
  </div>
</div>""", unsafe_allow_html=True)

tab_one, tab_batch, tab_eval = st.tabs(["One payment", "Batch", "Evaluation"])

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
                             reason=split_reason(d["reason"])[0]))
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
                                 decided_by=got.get("source"), expected=c.get("expected_action"),
                                 correct=got.get("correct"),
                                 reason=split_reason(got.get("reason") or "")[0]))

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
        view["action"] = view["action"].map(ACTION_TEXT)
        view["decided_by"] = view["decided_by"].map(lambda s: SOURCE_TEXT.get(s, s))
        view["category"] = view["category"].map(lambda s: CATEGORY_TEXT.get(s, s))
        if "expected" in view:
            view["expected"] = view["expected"].map(lambda s: ACTION_TEXT.get(s, s))
        st.dataframe(view, width="stretch", hide_index=True, column_config={
            "payment_id": st.column_config.TextColumn("Payment"),
            "amount": st.column_config.TextColumn("Amount"),
            "method": st.column_config.TextColumn("Method"),
            "channel": st.column_config.TextColumn("Channel"),
            "error_code": st.column_config.TextColumn("Error code"),
            "action": st.column_config.TextColumn("Recommendation", width="medium"),
            "category": st.column_config.TextColumn("Diagnosis"),
            "decided_by": st.column_config.TextColumn("Decided by"),
            "expected": st.column_config.TextColumn("Expected"),
            "correct": st.column_config.CheckboxColumn("Correct"),
            "reason": st.column_config.TextColumn("Reason", width="large"),
        })
        st.download_button("Download decisions (CSV)", view.to_csv(index=False), "ar3_decisions.csv",
                           "text/csv")

# ---------- Tab 3: evaluation ----------
with tab_eval:
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
  Fast tier <span class="mono">{config.FAST_MODEL}</span> · escalates to
  <span class="mono">{config.ULTRA_MODEL}</span> below confidence {config.CONFIDENCE_THRESHOLD}<br>
  Model calls today on this demo: {c['calls']} of {DAILY_LLM_CAP} ·
  <a href="{REPO_URL}">Source on GitHub</a>
</div>""", unsafe_allow_html=True)