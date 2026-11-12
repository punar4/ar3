# AR3 on PayPal failures the rule table doesn't know
31 held-out PayPal cases (labels written before any model run), 3 run(s).

| | Retry everything once | Rules only | AR3 with Nemotron |
| --- | --- | --- | --- |
| Correct decisions | 8/31 | 5/31 | 90% / 90% / 90% |
| Unsafe actions | 11 | 0 | 0 / 0 / 0 |
| Sent to a person | 0% | 100% | 16% |

Diagnosis accuracy (run 1): 97%. Who decided: {<Source.LLM_FAST: 'LLM_FAST'>: 21, <Source.LLM_ULTRA: 'LLM_ULTRA'>: 5, <Source.FALLBACK: 'FALLBACK'>: 5}. Median time: 3.5 s.
Confidence when the diagnosis was wrong: [0.9]
Same action in every run: 29/31 cases.

## By category (run 1)
| Category | Correct |
| --- | --- |
| GATEWAY_TEMPORARY | 6/6 |
| ISSUER_TEMPORARY | 4/4 |
| CUSTOMER_ACTION | 4/7 |
| HARD_DECLINE | 5/5 |
| RISK | 4/4 |
| UNKNOWN | 5/5 |

## Wrong decisions (run 1)
- 5650 "Strong customer authentication required by the issuer" (RECURRING, attempt 1): expected STOP, got RETRY_SCHEDULED via LLM_FAST (conf 0.80)
- 00N7 "CVV2_FAILURE: security code does not match" (LIVE_CHECKOUT, attempt 1): expected PROMPT_CUSTOMER, got STOP via LLM_FAST (conf 0.90)
- BILLING_AGREEMENT_CANCELLED "The buyer cancelled the billing agreement" (RECURRING, attempt 1): expected STOP, got RETRY_SCHEDULED via LLM_FAST (conf 0.85)