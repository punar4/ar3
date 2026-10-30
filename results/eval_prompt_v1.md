## Results (150 cases: 30 known codes, 120 messy)

| | Retry everything once | AR3, rules only | AR3 with Nemotron |
| --- | --- | --- | --- |
| Correct decisions, all cases | 33% | 31% | 87% |
| Correct decisions, messy cases | 32% | 13% | 83% |
| Unsafe actions | 50 | 0 | 0 |
| Sent to a human | 0% | 80% | 7% |

## Full AR3 details

- Diagnosis accuracy on messy cases: 92% (always guessing 'GATEWAY_TEMPORARY' would score 22%)
- Who decided: LLM_FAST 72%, RULE 20%, FALLBACK 7%, LLM_ULTRA 1%
- Median time per messy case: 1.1 s

## Cases AR3 got wrong (20)

| Case | Code | Description | Expected | Got | Decided by |
| --- | --- | --- | --- | --- | --- |
| tc_074 | INSUFF_BAL | Payer account has insufficient balance | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_075 | MANDATE_BAL | Mandate execution failed: balance insufficient | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_076 | NSF | Not sufficient funds in the linked account | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_078 | LOW_FUNDS | Insufficient credit limit on card | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_081 | TXN_DECLINED_BY_USER | Customer declined the collect request | PROMPT_CUSTOMER | STOP | LLM_FAST |
| tc_085 | DAILY_LIMIT | Payer has exceeded daily UPI transaction limit | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_089 | NB_USER_CANCEL | User cancelled at bank login page | PROMPT_CUSTOMER | STOP | LLM_FAST |
| tc_091 | LIMIT_EXCEEDED | Card's spending limit exceeded for the month | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_094 | BAL_LOW_AUTOPAY | AutoPay debit failed: account balance too low | RETRY_SCHEDULED | STOP | LLM_FAST |
| tc_095 | INV_CARD | Card number is not valid | PROMPT_CUSTOMER | STOP | LLM_FAST |
| tc_097 | CARD_EXPIRED | Card has expired | PROMPT_CUSTOMER | STOP | LLM_FAST |
| tc_099 | ACCT_CLOSED | Account linked to card is closed | PROMPT_CUSTOMER | STOP | LLM_FAST |
| tc_101 | INV_VPA | Invalid VPA, account does not exist | PROMPT_CUSTOMER | STOP | LLM_FAST |
| tc_104 | ACCT_DORMANT | Remitter account is dormant | PROMPT_CUSTOMER | STOP | LLM_FAST |
| tc_108 | NB_ACCT_CLOSED | Account closed | PROMPT_CUSTOMER | STOP | LLM_FAST |
| tc_126 | 05 | Do not honour | HUMAN_REVIEW | STOP | LLM_FAST |
| tc_127 | 05 | Do not honour | HUMAN_REVIEW | STOP | LLM_FAST |
| tc_131 | DECLINED | Transaction declined | HUMAN_REVIEW | STOP | LLM_FAST |
| tc_132 | DECLINED | Transaction declined | HUMAN_REVIEW | STOP | LLM_FAST |
| tc_137 | GENERIC_DECLINE | Your card was declined | HUMAN_REVIEW | STOP | LLM_FAST |

## Nemotron tiers on the 120 messy cases

| | Nano, reasoning off | Nano, reasoning on | Ultra, reasoning on |
| --- | --- | --- | --- |
| Diagnosis accuracy | 91% | 93% | 97% |
| Invalid replies | 0 | 0 | 0 |
| Median time | 1.1 s | 3.0 s | 2.0 s |
| Median tokens | 789 | 962 | 1061 |
| Confidences equal to a prompt example | 32/120 | 60/120 | 26/120 |