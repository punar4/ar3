# AR3

An open-source layer that works out why a UPI or card payment failed and recommends a safe next step. AI diagnoses, rules decide, and AR3 never moves money.

## Status

AR3 v2 is in progress for the Nebius × NVIDIA Global AI Hackathon (submission Oct 30, 2026). See CHANGES.md for progress.

Working now (43 tests passing):
- `rules.py`: known card and UPI error codes decided instantly, with different actions at checkout and on recurring payments
- `llm.py`: unclear errors go to Nemotron on Nebius Token Factory, fast model first, Ultra if the answer is invalid or unsure, human review if both fail
- `policy.py`: 7 independent safety checks that can override any decision
- `engine.py`: the full flow, end to end

Being built: the labelled test set and evaluation, and the demo.

## The problem

Gateways already retry failed payments, but many failures come back vague, like UPI's "debit failed", and nobody knows why. Retrying blindly wastes money and annoys banks and customers; giving up loses the sale.

## First finding: reasoning changes the diagnosis

Same failed payment (UPI error U30, "debit failed"), same model (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`), temperature 0. Only reasoning was switched on or off:

| | Reasoning on | Reasoning off |
| --- | --- | --- |
| Diagnosis | GATEWAY_TEMPORARY | HARD_DECLINE |
| Confidence | 0.85 | 0.95 |
| Time | 14.0 s | 2.5 s |
| Tokens | 405 | 145 |

The faster answer was more confident and probably wrong: "debit failed" is too vague to call a permanent decline. That's why AR3 never lets the model decide alone. One example isn't a conclusion; the full evaluation will measure this across the test set.

## How AR3 decides

1. Known error codes go to a rule table: instant, free and predictable.
2. Unclear errors go to NVIDIA Nemotron on Nebius Token Factory: a fast model first, Ultra only when it's unsure.
3. Every decision passes independent safety checks that can override it.
4. The output is a recommended action with a reason. The merchant's system carries it out; AR3 never moves money.

## Setup

Requires Python 3.14.

    git clone https://github.com/punar4/ar3.git
    cd ar3
    python -m venv venv
    venv\Scripts\activate        (Windows)
    source venv/bin/activate     (Mac/Linux)
    pip install -r requirements.txt

Copy `.env.example` to `.env` and add your Nebius Token Factory API key.

To check your key works: `python smoke_test.py` (lists the Nemotron models and makes one live call).

Run the tests (no API key needed): `pytest`

## License

MIT