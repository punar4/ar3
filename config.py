"""AR3 settings. Secrets (the API key) stay in .env; everything here is safe to publish."""

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

FAST_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
ULTRA_MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b"

FAST_THINKING = False    # fast tier: reasoning off (2.5 s vs 14 s in N1); revisit with T18 numbers
ULTRA_THINKING = True    # Ultra: reasoning on; it only sees hard cases
                         # None = don't send the switch at all

CONFIDENCE_THRESHOLD = 0.7    # below this, escalate (fast -> Ultra -> human review)
LLM_MAX_TOKENS = 4000         # generous: reasoning tokens count toward this (FEEDBACK #7)
LLM_TIMEOUT_SECONDS = 60

RETRY_CAP = 3                    # on attempt 3 or later, no more retries
MIN_WAIT_MINUTES = 15            # scheduled retries wait at least this long
HIGH_VALUE_PAISE = 5_000_000     # ₹50,000
HIGH_VALUE_MIN_WAIT_MINUTES = 30

ACQUIRERS = ["ACQ_A", "ACQ_B", "ACQ_C"]   # the merchant's acquirers (placeholder names)