"""AR3 settings. Secrets (the API key) stay in .env; everything here is safe to publish."""

import os

from dotenv import load_dotenv

load_dotenv()

# Which inference provider serves the models. Set AR3_PROVIDER=isoquant in .env to switch;
# nothing else in AR3 (prompt, rules, safety checks, decision code) changes.
PROVIDER = os.environ.get("AR3_PROVIDER", "nebius").lower()

if PROVIDER == "isoquant":
    BASE_URL = os.environ.get("ISOQUANT_BASE_URL", "")
    API_KEY_ENV = "ISOQUANT_API_KEY"
    FAST_MODEL = os.environ.get("ISOQUANT_FAST_MODEL", "")
    ULTRA_MODEL = os.environ.get("ISOQUANT_ULTRA_MODEL", "")
    THINKING_STYLE = os.environ.get("ISOQUANT_THINKING_STYLE") or "none"
elif PROVIDER == "nebius":
    BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
    API_KEY_ENV = "NEBIUS_API_KEY"
    # Defaults are the Nemotron models AR3 was built on. Set NEBIUS_FAST_MODEL / NEBIUS_ULTRA_MODEL
    # in .env to run other Token Factory models (used for same-model provider comparisons).
    FAST_MODEL = os.environ.get("NEBIUS_FAST_MODEL") or "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    ULTRA_MODEL = os.environ.get("NEBIUS_ULTRA_MODEL") or "nvidia/Nemotron-3-Ultra-550b-a55b"
    THINKING_STYLE = os.environ.get("NEBIUS_THINKING_STYLE") or "chat_template"
else:
    raise ValueError(f"Unknown AR3_PROVIDER: {PROVIDER!r} (use nebius or isoquant)")

# How reasoning is switched on and off (see llm.thinking_extra):
# chat_template | enable_thinking | thinking_type | reasoning_effort | none
# For reasoning_effort, the level names come from <PROVIDER>_REASONING_OFF / _ON in .env.
REASONING_OFF = os.environ.get(f"{PROVIDER.upper()}_REASONING_OFF", "")
REASONING_ON = os.environ.get(f"{PROVIDER.upper()}_REASONING_ON", "")

FAST_THINKING = False    # fast tier: reasoning off (2.5 s vs 14 s in N1); revisit with T18 numbers
ULTRA_THINKING = True    # Ultra: reasoning on; it only sees hard cases
                         # None = don't send the switch at all

SECOND_READ = True       # ask Nano twice (reasoning off, then on); if the two reads disagree on the
                         # cause, the case is uncertain whatever confidence the model printed
CONFIDENCE_THRESHOLD = 0.7    # below this, escalate (fast -> Ultra -> human review)
LLM_MAX_TOKENS = 4000         # generous: reasoning tokens count toward this (FEEDBACK #7)
LLM_TIMEOUT_SECONDS = 60

RETRY_CAP = 3                    # on attempt 3 or later, no more retries
MIN_WAIT_MINUTES = 15            # scheduled retries wait at least this long
HIGH_VALUE_PAISE = 5_000_000     # ₹50,000
HIGH_VALUE_MIN_WAIT_MINUTES = 30

USD_TO_INR = 88.0   # approximate; only used to apply the ₹ thresholds and ₹ summary to PayPal (USD) orders

ACQUIRERS =["ACQ_A", "ACQ_B", "ACQ_C"]   # the merchant's acquirers (placeholder names)