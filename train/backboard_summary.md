# Backboard model comparison

Live run on October 23, 2026. Three complete evaluations on the same 70 fictional development chats, each with
the common classification SYSTEM plus canonical SCHEMA in the user prompt and unchanged shared scoring.

| Model | Cases | Schema | Coverage | Risky flagged | False alarms | Signal precision | Signal recall | Avg s |
| --- | ---: | --- | --- | --- | --- | ---: | ---: | ---: |
| mistralai/mistral-small-3.1-24b-instruct | 70 | 70/70 | 70/70 | 36/36 valid (0 errors) | 3/34 valid (0 errors) | 0.852 | 0.981 | 9.6 |
| meta-llama/llama-3.3-70b-instruct | 70 | 69/70 | 69/70 | 36/36 valid (0 errors) | 3/33 valid (1 errors) | 0.912 | 0.981 | 9.33 |
| google/gemma-3-27b-it | 70 | 68/70 | 69/70 | 36/36 valid (0 errors) | 3/33 valid (1 errors) | 0.938 | 0.849 | 10.01 |

Qwen 2.5 72B: unavailable in live smoke (ReadTimeout after 120.654 s); no full result. An already-started retry
was canceled locally. No replacement model or invented 70-case Qwen scores are included.

Coverage includes usable partial analyses under guard/scoring.py. Gemma r06 retained two valid items after
discarding one malformed item, explaining strict schema 68/70 versus usable coverage 69/70. Gemma s33 and
Llama s16 were unusable safe answers; those errors are neither detections nor correct safe analyses.

Times include waiting for shared client request slots and must not be compared directly with local/Tinker
latency. All three models flagged the 36 risky development cases and raised three false alarms. These reused
cases are not an independent holdout or a real-world child-safety validation.

Actual Backboard billing: USD 0.034062 across 216 events, including all debug/smoke/Qwen requests and the 210
scored calls. Conservative token-price/reservation tracking: USD 0.065078, below the internal USD 1 cap.
