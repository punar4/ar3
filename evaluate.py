"""T18: evaluation. Every policy runs on the same labelled cases; prints the README tables.

python evaluate.py           # baseline ladder (calls Nemotron for the messy cases)
python evaluate.py --tiers   # also compares Nemotron tiers on the messy cases (more calls)
"""

import argparse
import json
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import config
import llm
from engine import decide
from policy import RETRIES
from schemas import Action, Channel, FailedPayment

CASES = json.loads(Path("data/test_cases.json").read_text())
MESSY = [c for c in CASES if c["kind"] == "messy"]
WORKERS = 4                                    # parallel API calls
EXAMPLE_CONFIDENCES = {0.85, 0.8, 0.35}        # the values used in the prompt's examples


def payment(case: dict) -> FailedPayment:
    return FailedPayment(**{k: v for k, v in case.items() if not k.startswith("expected") and k != "kind"})


def is_unsafe(case: dict, action: str) -> bool:
    """A retry that should never happen: possible fraud, a dead card, or past the retry cap."""
    if action not in RETRIES:
        return False
    return case["expected_category"] in {"RISK", "HARD_DECLINE"} or case["attempt_number"] >= config.RETRY_CAP


# ---------- The three policies ----------

def retry_all(case: dict) -> dict:
    p = payment(case)
    action = Action.RETRY_ALT_ACQUIRER if p.channel == Channel.LIVE_CHECKOUT else Action.RETRY_SCHEDULED
    return {"action": action, "category": None, "source": "BASELINE", "seconds": 0.0, "reason": ""}


def run_engine(case: dict, use_llm: bool) -> dict:
    start = time.perf_counter()
    d = decide(payment(case), use_llm=use_llm)
    return {"action": d.action, "category": d.category, "source": d.source,
            "seconds": time.perf_counter() - start, "reason": d.reason}


def run_policy(fn) -> list[dict]:
    with ThreadPoolExecutor(WORKERS) as pool:
        results = list(pool.map(fn, CASES))
    for case, r in zip(CASES, results):
        r["correct"] = r["action"] == case["expected_action"]
        r["unsafe"] = is_unsafe(case, r["action"])
    return results


def stats(results: list[dict], kind: str | None = None) -> dict:
    rows = [r for c, r in zip(CASES, results) if kind is None or c["kind"] == kind]
    return {
        "correct": 100 * sum(r["correct"] for r in rows) / len(rows),
        "unsafe": sum(r["unsafe"] for r in rows),
        "human": 100 * sum(r["action"] == Action.HUMAN_REVIEW for r in rows) / len(rows),
    }


# ---------- Optional: compare Nemotron tiers directly ----------

def ask_with_usage(model: str, thinking: bool, prompt: str) -> tuple[str, int, float]:
    start = time.perf_counter()
    response = llm._get_client().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": llm.SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=config.LLM_MAX_TOKENS,
        extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
    )
    return response.choices[0].message.content or "", response.usage.total_tokens, time.perf_counter() - start


def run_tier(model: str, thinking: bool) -> dict:
    def one(case):
        try:
            raw, tokens, seconds = ask_with_usage(model, thinking, llm.describe(payment(case)))
        except Exception:
            return None, 0, 0.0
        return llm.parse_reply(raw), tokens, seconds

    with ThreadPoolExecutor(WORKERS) as pool:
        out = list(pool.map(one, MESSY))
    replies = [r for r, _, _ in out]
    confidences = [r.confidence for r in replies if r]
    return {
        "accuracy": 100 * sum(1 for c, r in zip(MESSY, replies) if r and r.category == c["expected_category"]) / len(MESSY),
        "invalid": sum(r is None for r in replies),
        "seconds": statistics.median(s for _, _, s in out if s) if any(s for _, _, s in out) else 0.0,
        "tokens": statistics.median(t for _, t, _ in out if t) if any(t for _, t, _ in out) else 0,
        "anchored": sum(c in EXAMPLE_CONFIDENCES for c in confidences),
        "answered": len(confidences),
    }


# ---------- Report ----------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tiers", action="store_true", help="also compare Nemotron tiers (more API calls)")
    args = parser.parse_args()

    print(f"Running {len(CASES)} cases ({len(MESSY)} messy)...")
    names = ["Retry everything once", "AR3, rules only", "AR3 with Nemotron"]
    runs = [run_policy(retry_all),
            run_policy(lambda c: run_engine(c, use_llm=False)),
            run_policy(lambda c: run_engine(c, use_llm=True))]
    full = runs[2]
    all_s = [stats(r) for r in runs]
    messy_s = [stats(r, "messy") for r in runs]

    out = [f"## Results ({len(CASES)} cases: {len(CASES) - len(MESSY)} known codes, {len(MESSY)} messy)\n",
           "| | " + " | ".join(names) + " |", "| --- | --- | --- | --- |",
           "| Correct decisions, all cases | " + " | ".join(f"{s['correct']:.0f}%" for s in all_s) + " |",
           "| Correct decisions, messy cases | " + " | ".join(f"{s['correct']:.0f}%" for s in messy_s) + " |",
           "| Unsafe actions | " + " | ".join(str(s["unsafe"]) for s in all_s) + " |",
           "| Sent to a human | " + " | ".join(f"{s['human']:.0f}%" for s in all_s) + " |"]

    messy_full = [r for c, r in zip(CASES, full) if c["kind"] == "messy"]
    diag = 100 * sum(r["category"] == c["expected_category"] for c, r in zip(MESSY, messy_full)) / len(MESSY)
    common, count = Counter(c["expected_category"] for c in MESSY).most_common(1)[0]
    sources = Counter(str(r["source"]) for r in full)
    out += ["\n## Full AR3 details\n",
            f"- Diagnosis accuracy on messy cases: {diag:.0f}% (always guessing '{common}' would score {100 * count / len(MESSY):.0f}%)",
            "- Who decided: " + ", ".join(f"{k} {100 * v / len(CASES):.0f}%" for k, v in sources.most_common()),
            f"- Median time per messy case: {statistics.median(r['seconds'] for r in messy_full):.1f} s"]

    wrong = [(c, r) for c, r in zip(CASES, full) if not r["correct"]]
    out += [f"\n## Cases AR3 got wrong ({len(wrong)})\n",
            "| Case | Code | Description | Expected | Got | Decided by |", "| --- | --- | --- | --- | --- | --- |"]
    out += [f"| {c['payment_id']} | {c['error_code']} | {c['error_description']} | {c['expected_action']} | "
            f"{r['action']} | {r['source']} |" for c, r in wrong]

    if args.tiers:
        print("Comparing Nemotron tiers...")
        tiers = {"Nano, reasoning off": run_tier(config.FAST_MODEL, False),
                 "Nano, reasoning on": run_tier(config.FAST_MODEL, True),
                 "Ultra, reasoning on": run_tier(config.ULTRA_MODEL, True)}
        out += [f"\n## Nemotron tiers on the {len(MESSY)} messy cases\n",
                "| | " + " | ".join(tiers) + " |", "| --- | --- | --- | --- |",
                "| Diagnosis accuracy | " + " | ".join(f"{t['accuracy']:.0f}%" for t in tiers.values()) + " |",
                "| Invalid replies | " + " | ".join(str(t["invalid"]) for t in tiers.values()) + " |",
                "| Median time | " + " | ".join(f"{t['seconds']:.1f} s" for t in tiers.values()) + " |",
                "| Median tokens | " + " | ".join(f"{t['tokens']:.0f}" for t in tiers.values()) + " |",
                "| Confidences equal to a prompt example | " + " | ".join(f"{t['anchored']}/{t['answered']}" for t in tiers.values()) + " |"]

    report = "\n".join(out)
    print("\n" + report)
    Path("results").mkdir(exist_ok=True)
    Path("results/eval.md").write_text(report, encoding="utf-8")
    Path("results/full_decisions.json").write_text(json.dumps(
        [{**c, "got": r} for c, r in zip(CASES, full)], indent=2, default=str), encoding="utf-8")
    print("\nSaved results/eval.md and results/full_decisions.json")


if __name__ == "__main__":
    main()