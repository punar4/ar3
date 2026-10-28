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