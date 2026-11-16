Provider: nebius | fast: nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B | ultra: nvidia/Nemotron-3-Ultra-550b-a55b | 2026-11-16T21:15:28+00:00

## Results (150 cases: 30 known codes, 120 messy)

| | Retry everything once | AR3, rules only | AR3 with Nemotron |
| --- | --- | --- | --- |
| Correct decisions, all cases | 33% | 31% | 97% |
| Correct decisions, messy cases | 32% | 13% | 97% |
| Unsafe actions | 50 | 0 | 0 |
| Sent to a human | 0% | 80% | 12% |

## Full AR3 details

- Diagnosis accuracy on messy cases: 96% (always guessing 'GATEWAY_TEMPORARY' would score 22%)
- Who decided: LLM_FAST 66%, RULE 20%, FALLBACK 12%, LLM_ULTRA 2%
- Median time per messy case: 4.4 s

## Cases AR3 got wrong (4)

| Case | Code | Description | Expected | Got | Decided by |
| --- | --- | --- | --- | --- | --- |
| tc_078 | LOW_FUNDS | Insufficient credit limit on card | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_085 | DAILY_LIMIT | Payer has exceeded daily UPI transaction limit | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_107 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | STOP | HUMAN_REVIEW | FALLBACK |
| tc_122 | AML_HOLD | Transaction held for compliance review | STOP | HUMAN_REVIEW | FALLBACK |