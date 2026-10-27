# Feedback: Nebius Token Factory and Nemotron

Issues found while building AR3 for the Nebius × NVIDIA Global AI Hackathon.
Each entry: what I tried, what happened, and a suggested fix.

### 1. RuPay card fails with a generic error (Oct 19)
- **Tried:** Adding an Indian RuPay debit card in Token Factory Billing.
- **Happened:** Every attempt gave "Stripe error: unable to authenticate your payment method," with no hint that RuPay isn't supported. It took many retries to work out the card network was the cause.
- **Fix:** List supported card networks on the form; show a specific error for unsupported ones.

### 2. "No purchase necessary," but a card is needed in practice (Oct 19)
- **Tried:** Using hackathon credits without adding a card.
- **Happened:** The billing flow asked for a card before credits could be added, despite the rules. Students without international cards are blocked from the required platform.
- **Fix:** Allow promo or hackathon credits with no card, and make that path clear.

### 3. Billing docs contradict each other (Oct 20)
- **Tried:** Checking whether a card is required.
- **Happened:** Doc pages say a card is required, say it isn't, and say promo codes work without one. None matched the UI.
- **Fix:** One consistent billing page that matches the real UI flow.

### 4. Getting hackathon credits is unclear and slow (Oct 18–20)
- **Tried:** Finding the credit path from Devpost, then joining the Builder Program.
- **Happened:** No clear step from the hackathon page to Token Factory credits; I had to find and join the Builder Program separately. It needs an org or university email and about 2 business days of manual review. Codes went to the verification email, not the account email, and the approval email didn't include them.
- **Fix:** A "claim your hackathon credits" step on the Devpost page that credits the Token Factory account directly(i later contacted the supprt team directly and got the credits), or shows status and codes on the Builder Program page.

### 5. No usage alerts or spending caps (Oct 20)
- **Tried:** Setting a usage alert after adding a card.
- **Happened:** Token Factory has no alerts or budgets; only Nebius AI Cloud, a separate console, has them.
- **Fix:** Email alerts at 50%, 80% and 100% of credits, plus an optional hard cap that pauses API keys.

### 6. Positive: support resolved the credits issue quickly (Oct 20)
- **Tried:** Contacting Nebius support directly about not receiving my credits.
- **Happened:** A quick, smooth reply within about a day, and $25 credit ($29.50 incl. GST) was added.
- **Fix:** Keep it. Showing this support contact inside the credits flow would let others reach it sooner.

### 7. Nemotron on Token Factory: reasoning tokens and max_tokens aren't explained (Oct 22)
- **Tried:** `max_tokens=10` on `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (first seen in the Nebius course, module 1, Exercise 1).
- **Happened:** `content` was `None` with `finish_reason: length`. Nemotron reasons before answering and the reasoning tokens count toward `max_tokens`, so all 10 went to reasoning. That's expected for reasoning models, but nothing in the docs or the response explains it. An app that parses JSON (like AR3) would silently fail on every call.
- **Fix:** Document on the model page and API docs that reasoning tokens count toward `max_tokens`; show how to turn thinking off (`enable_thinking: False`) or read `reasoning_content`; signal clearly when only reasoning was produced.