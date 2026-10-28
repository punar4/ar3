"""N1 smoke test: one live Nemotron call through Nebius Token Factory that returns JSON."""

import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # reads .env and puts NEBIUS_API_KEY into the environment

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ["NEBIUS_API_KEY"],
)

# 1. Which Nemotron models can this key use? (exact IDs for config later)
print("Nemotron models on Token Factory:")
for model in client.models.list():
    if "nemotron" in model.id.lower():
        print("  ", model.id)

FAST_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

PROMPT = (
    'A UPI payment failed with error code U30 and description "debit failed". '
    "Reply with ONLY a JSON object with these keys: "
    '"category" (one of HARD_DECLINE, RISK, CUSTOMER_ACTION, ISSUER_TEMPORARY, '
    'GATEWAY_TEMPORARY, UNKNOWN), "reason" (one short sentence), '
    '"confidence" (a number from 0 to 1).'
)


def clean(text):
    """Remove ```json fences some models wrap around JSON."""
    text = text.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```")
    return text.strip()


def ask(thinking):
    start = time.perf_counter()
    response = client.chat.completions.create(
        model=FAST_MODEL,
        messages=[{"role": "user", "content": PROMPT}],
        temperature=0,
        max_tokens=2000,
        extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
    )
    seconds = time.perf_counter() - start
    choice = response.choices[0]

    print(f"\n--- thinking={thinking} | {seconds:.1f}s | "
          f"finish_reason={choice.finish_reason} | tokens={response.usage.total_tokens}")
    print("raw content:", choice.message.content)

    data = json.loads(clean(choice.message.content))  # fails loudly if not valid JSON
    print("parsed JSON OK:", data)


ask(thinking=True)
ask(thinking=False)