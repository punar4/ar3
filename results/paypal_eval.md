# AR3 on PayPal failures the rule table doesn't know
31 held-out PayPal cases (labels written before any model run), 2 run(s).

| | Retry everything once | Rules only | AR3 with Nemotron |
| --- | --- | --- | --- |
| Correct decisions | 8/31 | 5/31 | 97% (run 1), 94% (run 2) |
| Unsafe actions | 11 | 0 | 0 (run 1), 0 (run 2) |
| Sent to a person | 0% | 100% | 16% |

Diagnosis accuracy (run 1): 97%. Who decided: LLM_FAST 20, LLM_ULTRA 6, FALLBACK 5. Median time: 5.2 s.
Confidence when the diagnosis was wrong: [0.9]
Same action in every run: 28/31 cases.

## By category (run 1)
| Category | Correct |
| --- | --- |
| GATEWAY_TEMPORARY | 6/6 |
| ISSUER_TEMPORARY | 4/4 |
| CUSTOMER_ACTION | 6/7 |
| HARD_DECLINE | 5/5 |
| RISK | 4/4 |
| UNKNOWN | 5/5 |

## Wrong decisions (run 1)
- 5120 "INSUFFICIENT_FUNDS" (RECURRING, attempt 1): expected RETRY_SCHEDULED, got STOP via LLM_FAST (conf 0.92)