## Runs compared

| | nebius_run1 | nebius_run2 | isoquant_run1 | isoquant_run2 |
| --- | --- | --- | --- | --- |
| Provider | nebius | nebius | isoquant | isoquant |
| Fast model | nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B | nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B | deepseek-v4.1-flash-1017-fast | deepseek-v4.1-flash-1017-fast |
| Ultra model | nvidia/Nemotron-3-Ultra-550b-a55b | nvidia/Nemotron-3-Ultra-550b-a55b | glm-5.3-flash | glm-5.3-flash |
| Correct decisions | 97.3% | 98.7% | 98.0% | 97.3% |
| Unsafe actions | 0 | 0 | 0 | 0 |
| Sent to a person | 12% | 11% | 13% | 13% |
| Two reads disagreed | 3 | 0 | 0 | 1 |
| Decided by | LLM_FAST 99, RULE 30, FALLBACK 18, LLM_ULTRA 3 | LLM_FAST 99, RULE 30, FALLBACK 16, LLM_ULTRA 5 | LLM_FAST 101, RULE 30, FALLBACK 17, LLM_ULTRA 2 | LLM_FAST 100, RULE 30, FALLBACK 18, LLM_ULTRA 2 |
| Time per messy case, p50 | 4.4 s | 4.7 s | 0.9 s | 1.0 s |
| Time per messy case, p95 | 8.6 s | 8.7 s | 2.2 s | 2.7 s |
| Model calls | 246 | 244 | 242 | 243 |
| Failed calls | 0 | 0 | 0 | 0 |
| Invalid replies | 0 | 0 | 0 | 0 |
| Time per call, p50 | 1.88 s | 1.96 s | 0.41 s | 0.48 s |
| Input tokens | 291017 | 288658 | 274558 | 275635 |
|   of which cached | 0 | 0 | 243712 | 255552 |
| Output tokens | 60981 | 58649 | 22310 | 21836 |
| Cost per 1,000 payments | no price for nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B, nvidia/Nemotron-3-Ultra-550b-a55b | no price for nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B, nvidia/Nemotron-3-Ultra-550b-a55b | $0.071 | $0.067 |

## Decisions that changed between runs

**nebius_run1 vs nebius_run2** (same provider, run-to-run): 4 of 150 decisions differ

| Case | Code | Description | Expected | nebius_run1 | nebius_run2 |
| --- | --- | --- | --- | --- | --- |
| tc_078 | LOW_FUNDS | Insufficient credit limit on card | RETRY_SCHEDULED | STOP | RETRY_SCHEDULED |
| tc_091 | LIMIT_EXCEEDED | Card's spending limit exceeded for the month | RETRY_SCHEDULED | RETRY_SCHEDULED | STOP |
| tc_107 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | STOP | HUMAN_REVIEW | STOP |
| tc_122 | AML_HOLD | Transaction held for compliance review | STOP | HUMAN_REVIEW | STOP |

**nebius_run1 vs isoquant_run1** (different providers): 3 of 150 decisions differ

| Case | Code | Description | Expected | nebius_run1 | isoquant_run1 |
| --- | --- | --- | --- | --- | --- |
| tc_078 | LOW_FUNDS | Insufficient credit limit on card | RETRY_SCHEDULED | STOP | RETRY_SCHEDULED |
| tc_085 | DAILY_LIMIT | Payer has exceeded daily UPI transaction limit | RETRY_SCHEDULED | STOP | RETRY_SCHEDULED |
| tc_106 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | PROMPT_CUSTOMER | PROMPT_CUSTOMER | HUMAN_REVIEW |

**nebius_run1 vs isoquant_run2** (different providers): 4 of 150 decisions differ

| Case | Code | Description | Expected | nebius_run1 | isoquant_run2 |
| --- | --- | --- | --- | --- | --- |
| tc_078 | LOW_FUNDS | Insufficient credit limit on card | RETRY_SCHEDULED | STOP | RETRY_SCHEDULED |
| tc_085 | DAILY_LIMIT | Payer has exceeded daily UPI transaction limit | RETRY_SCHEDULED | STOP | RETRY_SCHEDULED |
| tc_106 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | PROMPT_CUSTOMER | PROMPT_CUSTOMER | HUMAN_REVIEW |
| tc_116 | VELOCITY | Velocity check failed: too many attempts in short time | STOP | STOP | HUMAN_REVIEW |

**nebius_run2 vs isoquant_run1** (different providers): 5 of 150 decisions differ

| Case | Code | Description | Expected | nebius_run2 | isoquant_run1 |
| --- | --- | --- | --- | --- | --- |
| tc_085 | DAILY_LIMIT | Payer has exceeded daily UPI transaction limit | RETRY_SCHEDULED | STOP | RETRY_SCHEDULED |
| tc_091 | LIMIT_EXCEEDED | Card's spending limit exceeded for the month | RETRY_SCHEDULED | STOP | RETRY_SCHEDULED |
| tc_106 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | PROMPT_CUSTOMER | PROMPT_CUSTOMER | HUMAN_REVIEW |
| tc_107 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | STOP | STOP | HUMAN_REVIEW |
| tc_122 | AML_HOLD | Transaction held for compliance review | STOP | STOP | HUMAN_REVIEW |

**nebius_run2 vs isoquant_run2** (different providers): 6 of 150 decisions differ

| Case | Code | Description | Expected | nebius_run2 | isoquant_run2 |
| --- | --- | --- | --- | --- | --- |
| tc_085 | DAILY_LIMIT | Payer has exceeded daily UPI transaction limit | RETRY_SCHEDULED | STOP | RETRY_SCHEDULED |
| tc_091 | LIMIT_EXCEEDED | Card's spending limit exceeded for the month | RETRY_SCHEDULED | STOP | RETRY_SCHEDULED |
| tc_106 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | PROMPT_CUSTOMER | PROMPT_CUSTOMER | HUMAN_REVIEW |
| tc_107 | TXN_NOT_PERMITTED | Transaction not permitted to cardholder | STOP | STOP | HUMAN_REVIEW |
| tc_116 | VELOCITY | Velocity check failed: too many attempts in short time | STOP | STOP | HUMAN_REVIEW |
| tc_122 | AML_HOLD | Transaction held for compliance review | STOP | STOP | HUMAN_REVIEW |

**isoquant_run1 vs isoquant_run2** (same provider, run-to-run): 1 of 150 decisions differ

| Case | Code | Description | Expected | isoquant_run1 | isoquant_run2 |
| --- | --- | --- | --- | --- | --- |
| tc_116 | VELOCITY | Velocity check failed: too many attempts in short time | STOP | STOP | HUMAN_REVIEW |
