# Strands and Laya: recorded decision model results

**Recorded 2 October 2026.** These are local measurements on an original synthetic
fixture. No customer data, production traces, or enterprise adoption claims are
included. [Methodology and reproduction commands](../README.md).

## What ran

Strands Decider 2B v19, Laya's English 421M checkpoint, and an untrained lexical
baseline answered the same Choice questions. Jev was **Not run**: no API key was
available, and no leaderboard results have been substituted.

The holdout contains **48 unique requests, 64 unique decisions, and 12 scenario
groups**. Each candidate completed three sequential trials: 144 timed requests
and 192 decision observations. Predictions were identical across those trials.
They remain 64 unique decisions, with correlated variants, rather than 192
independent samples. A separate 24-request, 32-decision calibration split selected
each gate before holdout execution.

## Holdout measurements

| Candidate | Correct decisions per trial | Accuracy | Request p50 | Request p95 |
|---|---:|---:|---:|---:|
| Strands Decider 2B v19 | 48 / 64 | 75.0% | 131.6 ms | 269.1 ms |
| Laya English 421M | 24 / 64 | 37.5% | 31.7 ms | 45.0 ms |
| Lexical baseline | 30 / 64 | 46.9% | 0.012 ms | 0.018 ms |
| Jev 1.13.0 | Not run | — | — | — |

No scored request failed execution or response validation. Accuracy includes all
attempted decisions. Latency is pooled across the three trials, at concurrency
one, including tokenization, all questions in the request, GPU synchronization,
and response validation. Three warmup requests and model initialization are
excluded. Two policy decisions share one timed request.

Strands' first holdout trial had a 336.2 ms p95; later trials were 204.2 and
203.1 ms. Laya's trial p95s were 45.9, 44.1, and 44.0 ms. The pooled numbers
therefore describe this sequence of repeated requests, not first-use service
latency or a production SLO.

### Calibration and fallback demand

The predeclared grid selects the highest coverage with at most 5% empirical
calibration error and at least 10 accepted calibration decisions.

| Candidate | Selected probability gate | Calibration accepted | Holdout accepted per trial | Holdout coverage | Error among accepted |
|---|---:|---:|---:|---:|---:|
| Strands | ≥ 0.90 | 12 / 32 | 11 / 64 | 17.2% | 0 / 11 |
| Laya | No qualifying gate | 0 / 32 | 0 / 64 | 0% | Undefined |
| Lexical baseline | No qualifying gate | 0 / 32 | 0 / 64 | 0% | Undefined |

Strands required fallback for **53 of 64 decisions (82.8%)**. Its zero observed
accepted errors come from only 11 unique accepted decisions and establish no
population error guarantee. Laya and the baseline abstained on every decision
under their fitted gates. Zero accepted unsafe predictions for an all-abstain
gate says nothing about useful autonomous coverage.

No fallback ran. End-to-end workflow quality, latency, and cost are unknown.
Hardware, energy, and API prices were not supplied; null cost fields mean unknown.

| Candidate | Multiclass Brier ↓ | NLL ↓ | ECE, 10 equal-width bins ↓ |
|---|---:|---:|---:|
| Strands | 0.257 | 0.406 | 0.173 |
| Laya | 0.666 | 1.059 | 0.281 |
| Lexical baseline | 0.592 | 0.947 | 0.083 |

These calibration statistics are descriptive on this small fixture. The lexical
baseline's lower ECE coexists with poor accuracy; ECE alone is not a selection
criterion.

## Where the models failed

| Task family | Decisions per trial | Strands accuracy | Laya accuracy | Lexical accuracy |
|---|---:|---:|---:|---:|
| Model routing | 16 | 100% | 25% | 43.8% |
| Tool selection | 16 | 100% | 25% | 43.8% |
| Policy classification | 32 | 50% | 50% | 50% |

Strands handled the routing and tool-selection cases in this fixture, including
their variants. Its policy answers exposed a question-sensitivity failure:
it returned the **same answer to opposite compliance and violation questions in
14 of 16 policy requests** per trial. All policy decisions fell below its fitted
gate. High aggregate accuracy would have hidden that failure family.

Laya was faster in this configuration, but selected incorrect routes and tools
and lost accuracy with added text. Original and reversed-option variants each
scored 50%; injection and irrelevant-text variants each scored 25%.

### Paired robustness checks

Each column compares a variant with the original over 16 unique holdout
decisions. Counts below show changed predictions, followed by how many changes
turned an originally correct prediction into an incorrect one.

| Candidate | Reversed options | Injected directive | Irrelevant context |
|---|---:|---:|---:|
| Strands | 0 changes; 0 degraded | 4 changes; 2 degraded | 0 changes; 0 degraded |
| Laya | 2 changes; 1 degraded | 6 changes; 5 degraded | 6 changes; 5 degraded |
| Lexical baseline | 0 changes; 0 degraded | 2 changes; 1 degraded | 4 changes; 2 degraded |

Strands' aggregate accuracy stayed at 75% across all four variants, despite the
injection changing four predictions. Improvements on two decisions offset two
degradations. Slice averages alone would have missed that instability.

## Reproduction conditions

- Machine: Apple M4 Pro, 48 GiB unified memory, macOS arm64; Python 3.13.12.
- Strands and Laya used the Mac GPU (`mps`) sequentially; the lexical baseline
  used the CPU. The same machine and frozen inputs were used for each candidate.
- Strands' backbone used bfloat16; Laya used float32. Compilation and Laya
  checkpoint routing were disabled. This compares the pinned implementations
  under these settings; it does not isolate architecture, parameter count, or
  numerical precision.
- The Strands runtime reported its reference causal-convolution implementation
  on this Mac. These timings do not predict performance with CUDA kernels.
- Laya used its English checkpoint, not its multilingual or typed-decisions
  checkpoint. No claim about those other checkpoints follows from this run.
- Both models received the same generic option descriptions and question
  instructions. No model-specific prompt optimization or holdout tuning was
  performed. The Choice-only policy probes use generic yes/no descriptions,
  making the question text necessary to distinguish compliance from violation.
  Other schemas and explicit task-specific option descriptions remain untested.
- Checkpoint and source revisions, effective temperatures, package versions,
  the model-runtime lock hash, and the benchmark protocol hash are in every
  model report. The complete [model pins](../models.json) and
  [runtime lockfile](../runtime/uv.lock) are committed.
- The frozen cases are English, public, small, and related to calibration task
  families. This is a starting fixture, not a JevBench reproduction, independent
  audit, security certification, or production reliability estimate.

## Inspect the evidence

| Candidate | Calibration | Fitted gate | Holdout outputs and timings |
|---|---|---|---|
| Strands | [JSON](2026-10-02/strands-calibration.json) | [JSON](2026-10-02/strands-gate.json) | [JSON](2026-10-02/strands-holdout.json) |
| Laya | [JSON](2026-10-02/laya-calibration.json) | [JSON](2026-10-02/laya-gate.json) | [JSON](2026-10-02/laya-holdout.json) |
| Lexical baseline | [JSON](2026-10-02/baseline-calibration.json) | [JSON](2026-10-02/baseline-gate.json) | [JSON](2026-10-02/baseline-holdout.json) |

The [comparison JSON](2026-10-02/comparison.json) and
[generated summary](2026-10-02/comparison.md) link the matching report hashes.
Raw reports preserve each decision's answer, probabilities, reference, error
status, family, variant, trial, and request timing. Content hashes detect
accidental edits; they are not signed execution attestations.

Original benchmark code and synthetic data use MIT-0. Upstream model and runtime
licenses remain Apache-2.0; weights are downloaded separately.
