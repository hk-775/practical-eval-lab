# Decision model comparison

Dataset: `enterprise-decisions-synthetic-v1` · split: **holdout**
48 unique requests; 64 unique decisions; 12 scenario groups; 3 trial(s).

| Candidate | Status | Accuracy | Brier | ECE | Coverage | Accepted error | Request p50 / p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | completed | 0.469 | 0.592 | 0.083 | 0.000 | — | 0.0 / 0.0 |
| strands | completed | 0.750 | 0.257 | 0.173 | 0.172 | 0.000 | 131.6 / 269.1 |
| laya | completed | 0.375 | 0.666 | 0.281 | 0.000 | — | 31.7 / 45.0 |
| jev | Not run | — | — | — | — | — | — |

## Interpretation

18 scenario groups. Variants are correlated. Calibration and holdout use related task families. This is an English starter benchmark, not production evidence. Repeated trials and variants are not independent samples. No production or safety certification. Hardware, dtype and runtime differ unless explicitly matched. No fallback was executed.

Coverage is the fraction accepted using top probability. Abstained and failed decisions require a fallback; fallback latency, quality and cost have not been measured. Costs remain unknown unless explicit assumptions were supplied.

No Jev comparison is established by an unexecuted adapter. The full JSON reports retain per-case outputs, probabilities, errors, model revisions, threshold provenance, and per-request timing.
