## Runs compared

| | full_decisions | isoquant_run1 | isoquant_run2 |
| --- | --- | --- | --- |
| Provider | ? | isoquant | isoquant |
| Fast model | ? | deepseek-v4.1-flash-1017-fast | deepseek-v4.1-flash-1017-fast |
| Ultra model | ? | glm-5.3-flash | glm-5.3-flash |
| Correct decisions | 98.7% | 98.0% | 97.3% |
| Unsafe actions | 0 | 0 | 0 |
| Sent to a person | 11% | 13% | 13% |
| Two reads disagreed | 2 | 0 | 1 |
| Decided by | LLM_FAST 98, RULE 30, FALLBACK 17, LLM_ULTRA 5 | LLM_FAST 101, RULE 30, FALLBACK 17, LLM_ULTRA 2 | LLM_FAST 100, RULE 30, FALLBACK 18, LLM_ULTRA 2 |
| Time per messy case, p50 | 3.6 s | 0.9 s | 1.0 s |
| Time per messy case, p95 | 10.9 s | 2.2 s | 2.7 s |
| Model calls | - | 242 | 243 |
| Failed calls | - | 0 | 0 |
| Invalid replies | - | 0 | 0 |
| Time per call, p50 | - | 0.41 s | 0.48 s |
| Input tokens | - | 274558 | 275635 |
|   of which cached | - | 243712 | 255552 |
| Output tokens | - | 22310 | 21836 |
| Cost per 1,000 payments | - | $0.071 | $0.067 |

## Decisions that changed between runs

**full_decisions vs isoquant_run1** (different providers): 3 of 150 decisions differ

| Case | Code | Description | Expected | full_decisions | isoquant_run1 |
| --- | --- | --- | --- | --- | --- |
| tc_085 | DAILY_LIMIT | Payer has exceeded daily UPI transaction limit | RETRY_SCHEDULED | STOP | RETRY_SCHEDULED |
| tc_106 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | PROMPT_CUSTOMER | PROMPT_CUSTOMER | HUMAN_REVIEW |
| tc_107 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | STOP | STOP | HUMAN_REVIEW |

**full_decisions vs isoquant_run2** (different providers): 4 of 150 decisions differ

| Case | Code | Description | Expected | full_decisions | isoquant_run2 |
| --- | --- | --- | --- | --- | --- |
| tc_085 | DAILY_LIMIT | Payer has exceeded daily UPI transaction limit | RETRY_SCHEDULED | STOP | RETRY_SCHEDULED |
| tc_106 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | PROMPT_CUSTOMER | PROMPT_CUSTOMER | HUMAN_REVIEW |
| tc_107 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | STOP | STOP | HUMAN_REVIEW |
| tc_116 | VELOCITY | Velocity check failed: too many attempts in short time | STOP | STOP | HUMAN_REVIEW |

**isoquant_run1 vs isoquant_run2** (same provider, run-to-run): 1 of 150 decisions differ

| Case | Code | Description | Expected | isoquant_run1 | isoquant_run2 |
| --- | --- | --- | --- | --- | --- |
| tc_116 | VELOCITY | Velocity check failed: too many attempts in short time | STOP | STOP | HUMAN_REVIEW |
