# AR3 on PayPal failures the rule table doesn't know
31 held-out PayPal cases (labels written before any model run), 3 run(s).

| | Retry everything once | Rules only | AR3 with Nemotron |
| --- | --- | --- | --- |
| Correct decisions | 8/31 | 5/31 | 94% / 94% / 94% |
| Unsafe actions | 11 | 0 | 0 / 0 / 0 |
| Sent to a person | 0% | 100% | 16% |

Diagnosis accuracy (run 1): 100%. Who decided: {<Source.LLM_FAST: 'LLM_FAST'>: 21, <Source.LLM_ULTRA: 'LLM_ULTRA'>: 5, <Source.FALLBACK: 'FALLBACK'>: 5}. Median time: 3.2 s.
Confidence when the diagnosis was wrong: none
Same action in every run: 31/31 cases.

## By category (run 1)
| Category | Correct |
| --- | --- |
| GATEWAY_TEMPORARY | 6/6 |
| ISSUER_TEMPORARY | 4/4 |
| CUSTOMER_ACTION | 5/7 |
| HARD_DECLINE | 5/5 |
| RISK | 4/4 |
| UNKNOWN | 5/5 |

## Wrong decisions (run 1)
- 5120 "INSUFFICIENT_FUNDS" (RECURRING, attempt 1): expected RETRY_SCHEDULED, got STOP via LLM_FAST (conf 0.90)
- 5130 "Exceeds the card's withdrawal amount limit" (RECURRING, attempt 1): expected RETRY_SCHEDULED, got STOP via LLM_FAST (conf 0.85)