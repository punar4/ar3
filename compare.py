"""Compare saved evaluation runs: accuracy, safety, stability between runs, speed and cost.

python compare.py results/decisions_nebius_run1.json results/decisions_isoquant_run1.json results/decisions_isoquant_run2.json
python compare.py <files...> --prices prices.json

prices.json (optional, US dollars per 1 million tokens, copied from each provider's pricing page):
{"model-id": {"in": 0.07, "out": 0.20, "cached": 0.014}}

Files written by `evaluate.py --label NAME` carry tokens and time per model call.
The older results/full_decisions.json also loads, but has no token counts.
"""

import argparse
import json
import statistics
from collections import Counter
from itertools import combinations
from pathlib import Path


def load(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):   # older format: a bare list of cases
        data = {"meta": {"provider": "?", "label": Path(path).stem}, "cases": data}
    data["name"] = data["meta"].get("label") or Path(path).stem
    return data


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))]


def summarise(run: dict, prices: dict) -> dict:
    cases = run["cases"]
    messy = [c for c in cases if c["kind"] == "messy"]
    calls = [call for c in cases for call in c["got"].get("calls", [])]
    ok = [call for call in calls if "error" not in call]
    seconds = [c["got"]["seconds"] for c in messy]
    row = {
        "Provider": run["meta"].get("provider", "?"),
        "Fast model": run["meta"].get("fast_model", "?"),
        "Ultra model": run["meta"].get("ultra_model", "?"),
        "Correct decisions": f"{100 * sum(c['got']['correct'] for c in cases) / len(cases):.1f}%",
        "Unsafe actions": sum(c["got"]["unsafe"] for c in cases),
        "Sent to a person": f"{100 * sum(c['got']['action'] == 'HUMAN_REVIEW' for c in cases) / len(cases):.0f}%",
        "Two reads disagreed": sum("reads disagreed" in c["got"]["reason"] for c in messy),
        "Decided by": ", ".join(f"{k} {v}" for k, v in Counter(c["got"]["source"] for c in cases).most_common()),
        "Time per messy case, p50": f"{percentile(seconds, 50):.1f} s",
        "Time per messy case, p95": f"{percentile(seconds, 95):.1f} s",
    }
    if calls:
        row["Model calls"] = len(calls)
        row["Failed calls"] = sum("error" in call for call in calls)
        row["Invalid replies"] = sum(not call["valid"] for call in ok)
        row["Time per call, p50"] = f"{statistics.median(call['seconds'] for call in ok):.2f} s" if ok else "-"
        row["Input tokens"] = sum(call["prompt_tokens"] for call in ok)
        row["  of which cached"] = sum(call["cached_tokens"] for call in ok)
        row["Output tokens"] = sum(call["completion_tokens"] for call in ok)
        cost, unpriced = 0.0, set()
        for call in ok:
            price = prices.get(call["model"])
            if price is None:
                unpriced.add(call["model"])
                continue
            cached = call["cached_tokens"]
            cost += ((call["prompt_tokens"] - cached) * price["in"] + cached * price.get("cached", price["in"])
                     + call["completion_tokens"] * price["out"]) / 1_000_000
        if prices and not unpriced:
            row["Cost per 1,000 payments"] = f"${1000 * cost / len(cases):.3f}"
        elif unpriced and prices:
            row["Cost per 1,000 payments"] = "no price for " + ", ".join(sorted(unpriced))
    return row


def flips(a: dict, b: dict) -> list[str]:
    """Cases where two runs chose a different action."""
    by_id = {c["payment_id"]: c for c in b["cases"]}
    out = []
    for c in a["cases"]:
        other = by_id.get(c["payment_id"])
        if other and c["got"]["action"] != other["got"]["action"]:
            out.append(f"| {c['payment_id']} | {c['error_code']} | {c['error_description']} | {c['expected_action']} "
                       f"| {c['got']['action']} | {other['got']['action']} |")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument("--prices", default="")
    parser.add_argument("--out", default="results/compare.md")
    args = parser.parse_args()

    prices = json.loads(Path(args.prices).read_text(encoding="utf-8")) if args.prices else {}
    runs = [load(f) for f in args.files]
    rows = [summarise(r, prices) for r in runs]

    keys = list(dict.fromkeys(k for row in rows for k in row))
    out = ["## Runs compared\n", "| | " + " | ".join(r["name"] for r in runs) + " |",
           "| --- |" + " --- |" * len(runs)]
    out += [f"| {k} | " + " | ".join(str(row.get(k, "-")) for row in rows) + " |" for k in keys]

    out.append("\n## Decisions that changed between runs\n")
    for a, b in combinations(runs, 2):
        changed = flips(a, b)
        same = a["meta"].get("provider") == b["meta"].get("provider")
        kind = "same provider, run-to-run" if same else "different providers"
        out.append(f"**{a['name']} vs {b['name']}** ({kind}): {len(changed)} of {len(a['cases'])} decisions differ\n")
        if changed:
            out += [f"| Case | Code | Description | Expected | {a['name']} | {b['name']} |",
                    "| --- | --- | --- | --- | --- | --- |", *changed, ""]

    report = "\n".join(out)
    print(report)
    Path(args.out).write_text(report, encoding="utf-8")
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
