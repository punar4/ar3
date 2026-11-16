## Runs compared

| | nebius_deepseek_run1 | nebius_deepseek_run2 | isoquant_run1 | isoquant_run2 |
| --- | --- | --- | --- | --- |
| Provider | nebius | nebius | isoquant | isoquant |
| Fast model | deepseek-ai/DeepSeek-V4.1-Flash-1017 | deepseek-ai/DeepSeek-V4.1-Flash-1017 | deepseek-v4.1-flash-1017-fast | deepseek-v4.1-flash-1017-fast |
| Ultra model | zai-org/GLM-5.3-Flash | zai-org/GLM-5.3-Flash | glm-5.3-flash | glm-5.3-flash |
| Correct decisions | 97.3% | 97.3% | 98.0% | 97.3% |
| Unsafe actions | 0 | 0 | 0 | 0 |
| Sent to a person | 13% | 13% | 13% | 13% |
| Two reads disagreed | 2 | 2 | 0 | 1 |
| Decided by | LLM_FAST 99, RULE 30, FALLBACK 19, LLM_ULTRA 2 | LLM_FAST 99, RULE 30, FALLBACK 19, LLM_ULTRA 2 | LLM_FAST 101, RULE 30, FALLBACK 17, LLM_ULTRA 2 | LLM_FAST 100, RULE 30, FALLBACK 18, LLM_ULTRA 2 |
| Time per messy case, p50 | 2.8 s | 2.8 s | 0.9 s | 1.0 s |
| Time per messy case, p95 | 4.9 s | 5.2 s | 2.2 s | 2.7 s |
| Model calls | 244 | 244 | 242 | 243 |
| Failed calls | 0 | 0 | 0 | 0 |
| Invalid replies | 0 | 0 | 0 | 0 |
| Time per call, p50 | 1.35 s | 1.37 s | 0.41 s | 0.48 s |
| Input tokens | 276711 | 276711 | 274558 | 275635 |
|   of which cached | 228352 | 247936 | 243712 | 255552 |
| Output tokens | 23746 | 22064 | 22310 | 21836 |
| Cost per 1,000 payments | $0.275 | $0.231 | $0.071 | $0.067 |

## Decisions that changed between runs

**nebius_deepseek_run1 vs nebius_deepseek_run2** (same provider, run-to-run): 0 of 150 decisions differ

**nebius_deepseek_run1 vs isoquant_run1** (different providers): 1 of 150 decisions differ

| Case | Code | Description | Expected | nebius_deepseek_run1 | isoquant_run1 |
| --- | --- | --- | --- | --- | --- |
| tc_116 | VELOCITY | Velocity check failed: too many attempts in short time | STOP | HUMAN_REVIEW | STOP |

**nebius_deepseek_run1 vs isoquant_run2** (different providers): 0 of 150 decisions differ

**nebius_deepseek_run2 vs isoquant_run1** (different providers): 1 of 150 decisions differ

| Case | Code | Description | Expected | nebius_deepseek_run2 | isoquant_run1 |
| --- | --- | --- | --- | --- | --- |
| tc_116 | VELOCITY | Velocity check failed: too many attempts in short time | STOP | HUMAN_REVIEW | STOP |

**nebius_deepseek_run2 vs isoquant_run2** (different providers): 0 of 150 decisions differ

**isoquant_run1 vs isoquant_run2** (same provider, run-to-run): 1 of 150 decisions differ

| Case | Code | Description | Expected | isoquant_run1 | isoquant_run2 |
| --- | --- | --- | --- | --- | --- |
| tc_116 | VELOCITY | Velocity check failed: too many attempts in short time | STOP | STOP | HUMAN_REVIEW |
