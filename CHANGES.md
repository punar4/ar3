# Changelog

AR3 v2, rebuilt from scratch for the Nebius × NVIDIA Global AI Hackathon.

## 2026-10-26

- New public repo with the MIT license and a Python .gitignore
- Virtual environment set up with Python 3.14 (not committed)
- Starter files: CHANGES.md and .env.example

## 2026-10-27

- requirements.txt with the 5 direct dependencies, pinned; fresh-venv install test passes
- FEEDBACK.md with 7 entries on Token Factory and Nemotron and Nebius X Nvidia course on Agentic AI
- README stub: status, problem, planned design, setup

## 2026-10-28

- schemas.py: enums, FailedPayment and Decision with Pydantic validation
- tests/test_schemas.py: 5 tests (negative/zero amount, "CASH", confidence 1.7 rejected); all pass
- smoke_test.py: live Nemotron call via Token Factory returns valid JSON; found exact model IDs; enable_thinking on vs off compared
- README: status updated; first finding (reasoning on vs off) added

## 2026-10-29

- rules.py: rule table for known card and UPI error codes, with different actions for live checkout and recurring payments; unknown codes go to Nemotron
- tests/test_rules.py: 14 tests (5 codes × 2 channels, unknown code, per-method codes, waits, normalisation); all pass
- config.py: model IDs, thinking settings and the 0.7 confidence threshold in one place
- llm.py: two-tier Nemotron diagnosis (Nano fast tier, then Ultra if the answer is invalid or below 0.7 confidence, then human review); every failure falls back safely
- tests/test_llm.py: 9 tests with a fake model (escalation, timeouts, invented action REROUTE_TO_CARD rejected, confidence 1.7 rejected); all pass
- live_check.py: real Nemotron run; vague UPI U30 now goes fast (unsure, 0.30) → Ultra (unsure, 0.35) → human review, instead of N1's confident "hard decline"
- policy.py: 7 independent safety checks that can override any decision, from rules or Nemotron; every override is recorded; 10 tests, all pass
- engine.py: the full flow (rules → Nemotron → safety checks → retry details), with idempotency keys, alternate-acquirer choice and a rules-only mode for the evaluation baseline; 5 end-to-end tests, all pass (43 total)