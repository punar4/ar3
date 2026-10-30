## Results (150 cases: 30 known codes, 120 messy)

| | Retry everything once | AR3, rules only | AR3 with Nemotron |
| --- | --- | --- | --- |
| Correct decisions, all cases | 33% | 31% | 98% |
| Correct decisions, messy cases | 32% | 13% | 98% |
| Unsafe actions | 50 | 0 | 0 |
| Sent to a human | 0% | 80% | 11% |

## Full AR3 details

- Diagnosis accuracy on messy cases: 99% (always guessing 'GATEWAY_TEMPORARY' would score 22%)
- Who decided: LLM_FAST 69%, RULE 20%, FALLBACK 11%, LLM_ULTRA 1%
- Median time per messy case: 0.9 s

## Cases AR3 got wrong (3)

| Case | Code | Description | Expected | Got | Decided by |
| --- | --- | --- | --- | --- | --- |
| tc_057 | RB_TIMEOUT | Remitter bank did not respond in time | PROMPT_CUSTOMER | RETRY_ALT_ACQUIRER | LLM_FAST |
| tc_083 | MANDATE_PAUSED | Customer has paused the AutoPay mandate | STOP | RETRY_SCHEDULED | LLM_FAST |
| tc_104 | ACCT_DORMANT | Remitter account is dormant | PROMPT_CUSTOMER | STOP | LLM_FAST |

## Nemotron tiers on the 120 messy cases

| | Nano, reasoning off | Nano, reasoning on | Ultra, reasoning on |
| --- | --- | --- | --- |
| Diagnosis accuracy | 97% | 96% | 94% |
| Invalid replies | 0 | 0 | 0 |
| Median time | 1.0 s | 2.2 s | 1.7 s |
| Median tokens | 1108 | 1308 | 1360 |
| Confidences equal to a prompt example | 45/120 | 55/120 | 22/120 |