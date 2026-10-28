# AR3

An open-source layer that works out why a UPI or card payment failed and recommends a safe next step. AI diagnoses, rules decide, and AR3 never moves money.

## Status

AR3 v2 is in progress for the Nebius × NVIDIA Global AI Hackathon (submission Oct 30, 2026). Right now the repo has the project setup only; the decision engine is being built. See CHANGES.md for progress.

## The problem

Gateways already retry failed payments, but many failures come back vague, like UPI's "debit failed", and nobody knows why. Retrying blindly wastes money and annoys banks and customers; giving up loses the sale.

## How AR3 will decide (design)

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

## License

MIT