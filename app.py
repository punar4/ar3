"""AR3 demo: decide one failed payment, run a batch, and see the evaluation.

Run locally:  streamlit run app.py
"""
import datetime as dt
import io
import json
import os
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

st.set_page_config(page_title="AR3: failed payment decisions", page_icon="💳", layout="wide")

BADGES = {
    "RULE": "🟦 Rule table (no model call)",
    "LLM_FAST": "🟩 Nemotron Nano (fast tier)",
    "LLM_ULTRA": "🟪 Nemotron Ultra (escalated)",
    "FALLBACK": "🟧 Both tiers unsure → human",
}
ACTION_TEXT = {
    "RETRY_ALT_ACQUIRER": "Retry now through another acquirer",
    "RETRY_SCHEDULED": "Retry later",
    "PROMPT_CUSTOMER": "Ask the customer",
    "STOP": "Stop: don't retry",
    "HUMAN_REVIEW": "Send to a human",
}
SAFE_NEXT_STEP = {"RETRY_ALT_ACQUIRER", "RETRY_SCHEDULED", "PROMPT_CUSTOMER"}

PRESETS = {
    "UPI AutoPay: bank down": dict(method="UPI", channel="RECURRING", error_code="BANK_503",
                                    error_description="Remitter bank CBS not available",
                                    amount_paise=49900, attempt_number=1),
    "Card checkout: gateway glitch": dict(method="CARD", channel="LIVE_CHECKOUT", error_code="PG_E102",
                                          error_description="Payment gateway internal error, please retry",
                                          amount_paise=129900, attempt_number=1),
    "UPI: vague 'debit failed' (U30)": dict(method="UPI", channel="LIVE_CHECKOUT", error_code="U30",
                                             error_description="debit failed",
                                             amount_paise=19900, attempt_number=1),
    "Card: suspected fraud (59)": dict(method="CARD", channel="LIVE_CHECKOUT", error_code="59",
                                       error_description="Suspected fraud",
                                       amount_paise=6_000_000, attempt_number=1),
    "Card renewal: low balance, 3rd attempt": dict(method="CARD", channel="RECURRING", error_code="51",
                                                   error_description="Insufficient funds",
                                                   amount_paise=49900, attempt_number=3),
    "UPI: compliance hold": dict(method="UPI", channel="RECURRING", error_code="AML_HOLD",
                                 error_description="Transaction held for compliance review",
                                 amount_paise=129900, attempt_number=1),
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


def rupees(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"


def show_decision(d: dict, capped: bool) -> None:
    st.subheader(ACTION_TEXT.get(d["action"], d["action"]))
    st.markdown(f"**Decided by:** {BADGES.get(d['source'], d['source'])}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Diagnosis", d["category"].replace("_", " ").title())
    c2.metric("Confidence", f"{d['confidence']:.2f}")
    c3.metric("Wait", f"{d['wait_minutes']} min" if d.get("wait_minutes") else "—")
    c4.metric("Time", f"{d.get('seconds', 0)} s")
    st.info(d["reason"])
    for check in d.get("overrides", []):
        st.warning(f"Safety check fired: **{check}**")
    if d.get("next_acquirer"):
        st.caption(f"Next acquirer: {d['next_acquirer']}")
    if d.get("idempotency_key"):
        st.caption(f"Idempotency key: `{d['idempotency_key']}` (a duplicated retry can't charge twice)")
    if capped:
        st.error("Today's demo limit for model calls is used up, so this unknown code went to a human.")


# ---------- Page ----------
st.title("AR3")
st.markdown("**Know why a payment failed before you retry it.**  \n"
            "Rules decide known error codes. NVIDIA Nemotron (on Nebius Token Factory) diagnoses messy ones. "
            "Independent safety checks have the final say. AR3 recommends; it never moves money.")

with st.sidebar:
    st.markdown("### Models")
    st.caption(f"Fast: `{config.FAST_MODEL}`")
    st.caption(f"Ultra: `{config.ULTRA_MODEL}`")
    st.caption(f"Escalate below confidence {config.CONFIDENCE_THRESHOLD}")
    st.markdown("### Demo limit")
    st.progress(min(llm_counter()["calls"] / DAILY_LLM_CAP, 1.0),
                text=f"Model calls today: {llm_counter()['calls']} / {DAILY_LLM_CAP}")
    st.caption("[Code on GitHub](https://github.com/punar4/ar3)")

tab_one, tab_batch, tab_eval = st.tabs(["Decide one payment", "Batch", "Evaluation"])

# ---------- Tab 1: one payment ----------
with tab_one:
    preset_name = st.selectbox("Start from an example", list(PRESETS))
    preset = PRESETS[preset_name]
    k = preset_name  # widget keys depend on the preset, so picking a preset refills the fields

    c1, c2, c3 = st.columns(3)
    methods, channels = [m.value for m in Method], [c.value for c in Channel]
    method = c1.selectbox("Method", methods, index=methods.index(preset["method"]), key=f"m_{k}")
    channel = c2.selectbox("Channel", channels, index=channels.index(preset["channel"]), key=f"c_{k}",
                           help="LIVE_CHECKOUT: the customer is waiting. RECURRING: a subscription or "
                                "AutoPay debit, customer not present.")
    attempt = c3.number_input("Attempt number", min_value=1, value=preset["attempt_number"], key=f"a_{k}")
    c4, c5 = st.columns([1, 2])
    code = c4.text_input("Error code", preset["error_code"], key=f"e_{k}")
    desc = c5.text_input("Error description", preset["error_description"], key=f"d_{k}")
    amount = st.number_input("Amount (₹)", min_value=1.0, value=preset["amount_paise"] / 100, key=f"r_{k}")

    if st.button("Decide", type="primary"):
        try:
            payment = FailedPayment(payment_id="demo_1", amount_paise=round(amount * 100), method=method,
                                    channel=channel, error_code=code, error_description=desc,
                                    attempt_number=attempt, acquirer="ACQ_A")
        except ValidationError as err:
            st.error(f"Check the fields: {err.errors()[0]['msg']}")
        else:
            with st.spinner("Deciding..."):
                decision, capped = run(payment)
            show_decision(decision, capped)

# ---------- Tab 2: batch ----------
with tab_batch:
    template = pd.DataFrame(TEMPLATE_ROWS).to_csv(index=False)
    st.download_button("Download the CSV template", template, "ar3_template.csv", "text/csv")
    upload = st.file_uploader(f"Upload failed payments (CSV or JSON, up to {MAX_BATCH_ROWS} rows)",
                              type=["csv", "json"])

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

        progress = st.progress(0.0, text="Deciding...")
        for n, p in enumerate(payments, start=1):
            d, capped = run(p)
            rows.append(dict(payment_id=p.payment_id, amount_paise=p.amount_paise, method=p.method.value,
                             channel=p.channel.value, error_code=p.error_code, action=d["action"],
                             category=d["category"], decided_by=d["source"], confidence=d["confidence"],
                             reason=d["reason"]))
            progress.progress(n / max(len(payments), 1), text=f"Decided {n} of {len(payments)}")
        progress.empty()
        if row_errors:
            with st.expander(f"{len(row_errors)} rows skipped"):
                st.write("\n".join(f"- {e}" for e in row_errors))
    else:
        path = Path("results/full_decisions.json")
        if path.exists():
            st.caption("No file uploaded, so this shows AR3's precomputed decisions on its 150 test cases.")
            for c in json.loads(path.read_text(encoding="utf-8")):
                got = c.get("got", {})
                rows.append(dict(payment_id=c["payment_id"], amount_paise=c["amount_paise"],
                                 method=c["method"], channel=c["channel"], error_code=c["error_code"],
                                 action=got.get("action"), category=got.get("category"),
                                 decided_by=got.get("source"), expected=c.get("expected_action"),
                                 correct=got.get("correct"), reason=got.get("reason")))

    if rows:
        df = pd.DataFrame(rows)
        at_risk = df["amount_paise"].sum()
        safe = df.loc[df["action"].isin(SAFE_NEXT_STEP), "amount_paise"].sum()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("₹ at risk", rupees(at_risk))
        m2.metric("₹ with a safe next step", rupees(safe))
        m3.metric("Stopped", int((df["action"] == "STOP").sum()))
        m4.metric("Sent to a human", int((df["action"] == "HUMAN_REVIEW").sum()))

        chosen = st.multiselect("Show actions", list(ACTION_TEXT), default=list(ACTION_TEXT),
                                format_func=lambda a: ACTION_TEXT[a])
        view = df[df["action"].isin(chosen)].copy()
        view.insert(1, "amount", view.pop("amount_paise").map(rupees))
        st.dataframe(view, width="stretch", hide_index=True)
        st.download_button("Download decisions (CSV)", view.to_csv(index=False), "ar3_decisions.csv",
                           "text/csv")

# ---------- Tab 3: evaluation ----------
with tab_eval:
    eval_path = Path("results/eval.md")
    if eval_path.exists():
        st.markdown(eval_path.read_text(encoding="utf-8"))
    else:
        st.info("Run `python evaluate.py --tiers` to create results/eval.md.")
    for label, name in [("Run 1: first prompt", "eval_prompt_v1.md"),
                        ("Run 2: prompt with the action table", "eval_prompt_v2.md")]:
        old = Path("results") / name
        if old.exists():
            with st.expander(f"Earlier run · {label}"):
                st.markdown(old.read_text(encoding="utf-8"))