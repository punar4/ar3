## Results (150 cases: 30 known codes, 120 messy)

| | Retry everything once | AR3, rules only | AR3 with Nemotron |
| --- | --- | --- | --- |
| Correct decisions, all cases | 33% | 31% | 95% |
| Correct decisions, messy cases | 32% | 13% | 93% |
| Unsafe actions | 50 | 0 | 0 |
| Sent to a human | 0% | 80% | 11% |

## Full AR3 details

- Diagnosis accuracy on messy cases: 97% (always guessing 'GATEWAY_TEMPORARY' would score 22%)
- Who decided: LLM_FAST 66%, RULE 20%, FALLBACK 11%, LLM_ULTRA 3%
- Median time per messy case: 3.0 s

## Cases AR3 got wrong (8)

| Case | Code | Description | Expected | Got | Decided by |
| --- | --- | --- | --- | --- | --- |
| tc_074 | INSUFF_BAL | Payer account has insufficient balance | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_075 | MANDATE_BAL | Mandate execution failed: balance insufficient | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_076 | NSF | Not sufficient funds in the linked account | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_078 | LOW_FUNDS | Insufficient credit limit on card | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_085 | DAILY_LIMIT | Payer has exceeded daily UPI transaction limit | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_091 | LIMIT_EXCEEDED | Card's spending limit exceeded for the month | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_094 | BAL_LOW_AUTOPAY | AutoPay debit failed: account balance too low | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_107 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | STOP | HUMAN_REVIEW | FALLBACK |