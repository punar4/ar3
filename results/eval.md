## Results (150 cases: 30 known codes, 120 messy)

| | Retry everything once | AR3, rules only | AR3 with Nemotron |
| --- | --- | --- | --- |
| Correct decisions, all cases | 33% | 31% | 99% |
| Correct decisions, messy cases | 32% | 13% | 98% |
| Unsafe actions | 50 | 0 | 0 |
| Sent to a human | 0% | 80% | 11% |

## Full AR3 details

- Diagnosis accuracy on messy cases: 97% (always guessing 'GATEWAY_TEMPORARY' would score 22%)
- Who decided: LLM_FAST 65%, RULE 20%, FALLBACK 11%, LLM_ULTRA 3%
- Median time per messy case: 3.6 s

## Cases AR3 got wrong (2)

| Case | Code | Description | Expected | Got | Decided by |
| --- | --- | --- | --- | --- | --- |
| tc_085 | DAILY_LIMIT | Payer has exceeded daily UPI transaction limit | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_122 | AML_HOLD | Transaction held for compliance review | STOP | HUMAN_REVIEW | FALLBACK |