"""Find out how the current provider switches reasoning on and off for AR3's two models.

python reasoning_probe.py     # about 20 small live calls on the provider and models set in .env

Sends one vague payment (UPI U30, "debit failed") with each known way of setting reasoning,
and prints what came back. A setting works if its on and off rows clearly differ in tokens or time.
"""

import time
from concurrent.futures import ThreadPoolExecutor

import config
import llm
from schemas import FailedPayment

PAYMENT = FailedPayment(payment_id="probe_1", amount_paise=49900, method="UPI", channel="RECURRING",
                        error_code="U30", error_description="debit failed")

VARIANTS = [
    ("nothing sent", {}),
    ("chat_template  off", {"chat_template_kwargs": {"enable_thinking": False}}),
    ("chat_template  on", {"chat_template_kwargs": {"enable_thinking": True}}),
    ("enable_thinking  off", {"enable_thinking": False}),
    ("enable_thinking  on", {"enable_thinking": True}),
    ("thinking_type  off", {"thinking": {"type": "disabled"}}),
    ("thinking_type  on", {"thinking": {"type": "enabled"}}),
    ("reasoning_effort  none", {"reasoning_effort": "none"}),
    ("reasoning_effort  low", {"reasoning_effort": "low"}),
    ("reasoning_effort  high", {"reasoning_effort": "high"}),
]


def one(job: tuple[str, str, dict]) -> str:
    model, label, body = job
    start = time.perf_counter()
    try:
        r = llm._get_client().chat.completions.create(
            model=model, temperature=0, max_tokens=config.LLM_MAX_TOKENS,
            messages=[{"role": "system", "content": llm.SYSTEM_PROMPT},
                      {"role": "user", "content": llm.describe(PAYMENT)}],
            extra_body=body,
        )
    except Exception as error:
        return f"{label:<24} ERROR  {str(error)[:110]}"
    seconds = time.perf_counter() - start
    message = r.choices[0].message
    details = getattr(r.usage, "completion_tokens_details", None)
    reasoning_tokens = getattr(details, "reasoning_tokens", None)
    extra = message.model_extra or {}
    shown = bool(getattr(message, "reasoning_content", None) or extra.get("reasoning_content") or extra.get("reasoning"))
    reply = llm.parse_reply(message.content or "")
    answer = f"{reply.category} {reply.confidence:.2f}" if reply else "invalid reply"
    return (f"{label:<24} out={r.usage.completion_tokens:<5} reasoning_tokens={str(reasoning_tokens):<5} "
            f"reasoning_text={'yes' if shown else 'no':<3} {seconds:5.1f}s  {answer}")


def main() -> None:
    print(f"Provider: {config.PROVIDER}")
    for model in dict.fromkeys([config.FAST_MODEL, config.ULTRA_MODEL]):
        print(f"\n{model}")
        with ThreadPoolExecutor(5) as pool:
            for line in pool.map(one, [(model, label, body) for label, body in VARIANTS]):
                print("  " + line)


if __name__ == "__main__":
    main()
