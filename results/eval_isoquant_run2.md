Provider: isoquant | fast: deepseek-v4.1-flash-1017-fast | ultra: glm-5.3-flash | 2026-11-16T20:48:58+00:00

## Results (150 cases: 30 known codes, 120 messy)

| | Retry everything once | AR3, rules only | AR3 with Nemotron |
| --- | --- | --- | --- |
| Correct decisions, all cases | 33% | 31% | 97% |
| Correct decisions, messy cases | 32% | 13% | 97% |
| Unsafe actions | 50 | 0 | 0 |
| Sent to a human | 0% | 80% | 13% |

## Full AR3 details

- Diagnosis accuracy on messy cases: 95% (always guessing 'GATEWAY_TEMPORARY' would score 22%)
- Who decided: LLM_FAST 67%, RULE 20%, FALLBACK 12%, LLM_ULTRA 1%
- Median time per messy case: 1.0 s

## Cases AR3 got wrong (4)

| Case | Code | Description | Expected | Got | Decided by |
| --- | --- | --- | --- | --- | --- |
| tc_106 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | PROMPT_CUSTOMER | HUMAN_REVIEW | FALLBACK |
| tc_107 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | STOP | HUMAN_REVIEW | LLM_FAST |
| tc_116 | VELOCITY | Velocity check failed: too many attempts in short time | STOP | HUMAN_REVIEW | LLM_FAST |
| tc_122 | AML_HOLD | Transaction held for compliance review | STOP | HUMAN_REVIEW | FALLBACK |