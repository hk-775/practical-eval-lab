# Decision model diagnostic: Strands and Laya

**Design review: exploratory fixture, not a model-selection benchmark.**
The first run has only 12 holdout scenario groups, incomplete calibration class
coverage, and policy option wording that exercises a documented Laya limitation.
Read the [design review and replacement plan](DESIGN_REVIEW.md) before interpreting
the scores. The raw recordings are preserved; their aggregate accuracy does not
establish a general model ranking.

Compare pinned local decision models on the same frozen English cases, with a
lexical reference and an optional Jev adapter. This source-checkout benchmark is
separate from the lab's six teaching suites and their recorded rule-based results.

**Initial diagnostic:** Strands Decider 2B v19 and Laya's English checkpoint.
Both run locally without a model API key. The first download requires access to
their public Hugging Face repositories. Jev remains **not run** unless an actual
authenticated report is supplied; its adapter is not evidence of its performance.

[Recorded results: 2 October 2026](recordings/README.md) includes the local
measurements, calibration gates, per-case outputs, and interpretation.

## What this evaluates

The v1 contract is **Choice only**: state text plus named options in, a selected
option and a full probability distribution out. It exercises:

- Model routing: simple tasks, reasoning, software tasks, and missing context.
- Tool selection: reads, explicitly requested changes, and clarification.
- Policy classification: compliance and violation questions over the same state.
- Robustness: reversed option order, injected instructions, and irrelevant text.

These questions do not execute tools, models selected by a router, or enterprise
workflows. Correctly classifying an action does not establish that an authorization
system enforces it.

### Frozen data

| Split | Requests | Decisions | Scenario groups |
|---|---:|---:|---:|
| Calibration | 24 | 32 | 6 |
| Holdout | 48 | 64 | 12 |

All 18 scenarios are original synthetic data under MIT-0. Four related variants
stay together in one split. Policy requests contain two questions; the other
requests contain one. The [manifest](data/manifest.json) pins JSONL byte hashes.
[Authoring source](build_cases.py) makes the cases reviewable; CI checks that it
still reproduces the frozen artifacts. Revise the dataset version when changing
cases, references, or partitioning.

The holdout is public and small. Its families resemble calibration families.
Variants and repeated trials are correlated. Results are descriptive checks on
this fixture, not estimates of production reliability, a sealed generalization
test, or a claim to reproduce JevBench. Model code receives no reference answers,
unsafe-answer labels, case IDs, or family labels.

## Quick check without model downloads

From the repository root:

```sh
uv sync --locked
uv run --locked python -m benchmarks.decision_models validate
uv run --locked python -m benchmarks.decision_models run \
  --candidate baseline --split calibration \
  --out local/decision-models/baseline-calibration.json
uv run --locked python -m benchmarks.decision_models calibrate \
  local/decision-models/baseline-calibration.json \
  --out local/decision-models/baseline-gate.json
uv run --locked python -m benchmarks.decision_models run \
  --candidate baseline --split holdout \
  --gate local/decision-models/baseline-gate.json \
  --out local/decision-models/baseline-holdout.json
```

The lexical baseline compares word overlap with option descriptions and maps
similarities through a softmax. Its probabilities are untrained. It is a cheap
reference, not a substitute for either model or an oracle.

## Run Strands and Laya locally

Heavy model dependencies have their own [project](runtime/pyproject.toml) and
[lockfile](runtime/uv.lock). They are not installed with the ordinary lab.
Use Python 3.11–3.13 for this environment:

```sh
uv sync --locked --project benchmarks/decision_models/runtime
```

Run from the repository root. This example uses Apple Silicon's GPU; choose
`--device cuda` for a supported NVIDIA GPU or `--device cpu` for CPU:

```sh
uv run --locked --project benchmarks/decision_models/runtime \
  python -m benchmarks.decision_models run \
  --candidate strands --device mps --split calibration \
  --out local/decision-models/strands-calibration.json

uv run --locked python -m benchmarks.decision_models calibrate \
  local/decision-models/strands-calibration.json \
  --max-error 0.05 --min-accepted 10 \
  --out local/decision-models/strands-gate.json

uv run --locked --project benchmarks/decision_models/runtime \
  python -m benchmarks.decision_models run \
  --candidate strands --device mps --split holdout \
  --gate local/decision-models/strands-gate.json \
  --out local/decision-models/strands-holdout.json
```

Repeat with `--candidate laya` and `laya-` output filenames. Run candidates
sequentially on an otherwise idle machine. The default is one trial; `--trials 3`
repeats the measured split and retains individual observations. Fit gates using
one calibration trial, then use the same holdout trial count for every candidate.

### Exact models and inference settings

[models.json](models.json) pins the public checkpoint and source commits:

- **Strands:** `StrandsAgents/strands-decider-2B-hobson-v19`, adapter revision
  `bb282d786bc251fd4e3068de3ada9ddbb38127cd`, source `ddd11994…`.
  The Qwen backbone is explicitly downloaded at `b1485b2f…`. Upstream provenance
  calls that backbone revision inferred from training time; we pin it for this
  inference run without claiming independent reconstruction of training.
  The adapter uses a temporary config to point to the pinned snapshot, preserving
  the upstream cache. Input overflow is rejected with `strict_window=True`.
- **Laya:** `convaiinnovations/laya`, English checkpoint revision
  `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`, source `fa9a2a70…`.
  The checkpoint router, compilation, and optional fast kernels are disabled.
  Its 512-token context and 192-token head budgets are explicit. Reported state
  truncation or collapsed options count as failed requests.
- The shipped inference precision and temperatures are recorded, not silently
  equalized. On the initial Mac setup Laya uses float32 and Strands uses bfloat16
  for its backbone. This compares complete implementations, not a controlled
  same-size or same-precision architecture ablation.
- Laya's runtime clamps an out-of-range temperature for its `choice:11+` bucket.
  This dataset uses 2–4 options, so that bucket is not exercised. Effective
  temperatures are retained in every local model report.
- The model loaders use public safetensors checkpoints. No weights are bundled
  in this repository. Upstream software and model licenses remain Apache-2.0.

## Gate selection and metrics

The gate uses **top-option probability**, not a vendor-specific confidence field.
`calibrate` selects the maximum coverage satisfying the requested empirical error
limit and minimum accepted count from a fixed threshold grid:
`0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0`.
If none qualifies, the threshold is null and every decision requires fallback.
The gate records its calibration hash, candidate identity, protocol hash, and
scenario groups. It cannot be applied to a different candidate or overlapping
holdout groups.

The default 5% limit is a **calibration-sample criterion**, not a statistical
guarantee. A model can exceed it on holdout. The minimum count is decisions,
including related variants, not independent groups. Production deployment would
require a much larger representative evaluation and uncertainty analysis.

Reports include:

| Metric | Definition and denominator |
|---|---|
| Accuracy | Correct decisions / all attempted decisions; failures count as incorrect |
| Brier | Mean sum of squared probability errors across options; valid decisions only, range 0–2 |
| NLL | Mean negative log probability of the reference; valid decisions only, probabilities floored at `1e-15` |
| ECE | Top-label calibration error over 10 equal-width probability bins; valid decisions only |
| Coverage | Accepted decisions / all attempted decisions |
| Accepted error | Incorrect accepted decisions / accepted decisions; null when none accepted |
| Unsafe acceptance | Accepted unsafe predictions / decisions with a listed unsafe option |
| Request latency | Client wall time, including tokenization, all questions, and response validation; p50/p95 use linear interpolation |
| Slices | The same metrics by task family and variant |

The full probability distribution, reference, selected option, native confidence,
error code, and model identity are retained per decision. Rounded distributions
within 0.001 of unit mass are normalized for scoring and their original sum is
recorded. Missing labels, non-finite probabilities, inconsistent choices, or
model-version mismatches fail validation.

Each run performs three excluded synthetic warmup requests. The first probe is
recorded separately; it is not a general cold-start guarantee. Model initialization
and downloads are timed separately. Measured requests run sequentially with GPU
synchronization and no automatic HTTP retries. There is no concurrency benchmark.
Repeated trials retain their own latency summaries.

**Cost and fallback:** no hardware, energy, or API price is invented. Optional
`--input-usd-per-million` and `--compute-usd-per-hour` arguments produce explicitly
labeled estimates for measured requests. Setup, warmup, idle time, operations,
output charges, and fallback are excluded. Token accounting differs by runtime.
Null cost means unknown, not free. Fallback demand is measured; no fallback is
executed, so end-to-end workflow quality, latency, and cost remain unknown.

## Compare recorded evidence

```sh
uv run --locked python -m benchmarks.decision_models compare \
  local/decision-models/baseline-holdout.json \
  local/decision-models/strands-holdout.json \
  local/decision-models/laya-holdout.json \
  --out local/decision-models/comparison.json \
  --markdown local/decision-models/comparison.md
```

Comparison rejects mismatched datasets, splits, trial counts, protocols, and
threshold-selection methods. Hardware and precision are shown for review.
Absent candidates are shown as **not run**, without borrowed leaderboard scores.
Reports carry content hashes for accidental-change detection; these hashes do not
authenticate a machine, prove execution, or provide a signed attestation.

The benchmark CLI exits 0 after a completed report, 2 for invalid setup/configuration,
and 3 when a scored run contains execution or response-contract failures. A low
accuracy or an all-abstain gate is a measured result, not an execution error.
Raw run files go under ignored `local/`. Publishing a result requires deliberate
review and copying of the selected synthetic recordings.

## Optional Jev

Jev is pinned to `jev-1.13.0` and requires `TYPESAFE_API_KEY` supplied through the
environment. The adapter sends only the public synthetic state and questions to
TypeSafe. It refuses redirects and does not retry; it never prints the credential
or response body on failure. With no key it exits **not run** before network setup.
Unit tests use a mocked HTTP response and provide no Jev quality or latency evidence.

```sh
# With a key already supplied securely through your environment:
uv run --locked python -m benchmarks.decision_models run \
  --candidate jev --split calibration \
  --out local/decision-models/jev-calibration.json
```

## Verify

```sh
uv run --locked python -m benchmarks.decision_models.build_cases --check
uv run --locked pytest -q tests/test_decision_models.py
```

CI validates the frozen data, metrics, gate isolation, response contract, and
missing-key behavior without downloading weights or calling model APIs.

## Sources and scope

- [Strands source and evaluation](https://github.com/strands-labs/strands-decider/tree/ddd11994bc451ffc78fa30f43037c291fd4d44b6)
- [Strands checkpoint](https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v19/tree/bb282d786bc251fd4e3068de3ada9ddbb38127cd)
- [Laya source](https://github.com/NandhaKishorM/laya/tree/fa9a2a7070b1789912a49ae24603bbfb1a78b001)
- [Laya checkpoint](https://huggingface.co/convaiinnovations/laya/tree/55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851)
- [TypeSafe API](https://docs.typesafe.ai/api) and [confidence definitions](https://docs.typesafe.ai/confidence)

AxonLLM is a possible downstream routing integration. This benchmark does not
currently call AxonLLM, Ostiari, or Escape Lab. AWS infrastructure remains not
applicable: execution is local, Jev is optional, and the public documentation is static.
