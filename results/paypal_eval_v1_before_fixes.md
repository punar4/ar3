# AR3 on PayPal failures the rule table doesn't know
31 held-out PayPal cases (labels written before any model run), 3 run(s).

| | Retry everything once | Rules only | AR3 with Nemotron |
| --- | --- | --- | --- |
| Correct decisions | 8/31 | 5/31 | 77% / 81% / 81% |
| Unsafe actions | 11 | 0 | 0 / 0 / 0 |
| Sent to a person | 0% | 100% | 6% |

Diagnosis accuracy (run 1): 71%. Who decided: {<Source.LLM_FAST: 'LLM_FAST'>: 28, <Source.LLM_ULTRA: 'LLM_ULTRA'>: 1, <Source.FALLBACK: 'FALLBACK'>: 2}. Median time: 0.7 s.
Confidence when the diagnosis was wrong: [0.75, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.95]
Same action in every run: 28/31 cases.

## By category (run 1)
| Category | Correct |
| --- | --- |
| GATEWAY_TEMPORARY | 5/6 |
| ISSUER_TEMPORARY | 4/4 |
| CUSTOMER_ACTION | 5/7 |
| HARD_DECLINE | 5/5 |
| RISK | 3/4 |
| UNKNOWN | 2/5 |

## Wrong decisions (run 1)
- RATE_LIMIT_REACHED "Too many requests. Try again shortly" (LIVE_CHECKOUT, attempt 1): expected RETRY_ALT_ACQUIRER, got STOP via LLM_FAST (conf 0.90)
- 00N7 "CVV2_FAILURE: security code does not match" (LIVE_CHECKOUT, attempt 1): expected PROMPT_CUSTOMER, got STOP via LLM_FAST (conf 0.95)
- BILLING_AGREEMENT_CANCELLED "The buyer cancelled the billing agreement" (RECURRING, attempt 1): expected STOP, got RETRY_SCHEDULED via LLM_FAST (conf 0.75)
- PICKUP_CARD "Issuer asks the merchant to retain the card" (LIVE_CHECKOUT, attempt 1): expected STOP, got PROMPT_CUSTOMER via LLM_FAST (conf 0.90)
- 0500 "DO_NOT_HONOR" (LIVE_CHECKOUT, attempt 1): expected HUMAN_REVIEW, got PROMPT_CUSTOMER via LLM_FAST (conf 0.90)
- PROCESSOR_DECLINED "Declined" (RECURRING, attempt 1): expected HUMAN_REVIEW, got STOP via LLM_FAST (conf 0.90)
- HTTP_400 "" (LIVE_CHECKOUT, attempt 1): expected HUMAN_REVIEW, got STOP via LLM_FAST (conf 0.90)