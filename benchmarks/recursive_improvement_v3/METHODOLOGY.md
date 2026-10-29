# Workflow recovery: methods and reproduction

[Read the short study](README.md) · [Inspect all recorded results](recordings/README.md)

## The walkthrough trace

The [short study](README.md) illustrates a recorded final-test case from a selected
random-search policy. It was chosen after the run for explanation, not used to
select or tune a policy. It does not establish a typical success rate.

The complete trace includes cancellation and a rejected excessive refund proposal.
The policy repairs the amount; the walkthrough starts at step 6, when the authorized
refund commits but the provider returns an unknown outcome. Receipt lookup then
misses. Retrying the exact request and idempotency key returns the original receipt,
with no new refund effect. Access is updated and final state verified.

[Download the complete verified trace](refund-recovery-trace.json).
The export omits runtime timings and is checked against the original behavioral
trace hash during every site build. It contains synthetic identifiers only.

To reconstruct it from the source checkout:

```bash
uv sync --locked
uv run --locked python -m benchmarks.recursive_improvement_v3 inspect \
  benchmarks/recursive_improvement_v3/recordings/2026-10-29 \
  --batch 106aa26af565b68744e32f2adbe46d16f7105744f4c5082ff1696944243dce48 \
  --case test-3617f52ad08efc42-0 --out reports/refund-recovery-trace.json
```

Use a fresh output file. The inspector verifies the behavioral trace commitment;
new local timing fields are not the recorded run's timings.

Diagram companions: [static SVG](../../docs/architecture/refund-recovery.svg) ·
[static PNG](../../docs/architecture/refund-recovery.png) ·
[editable draw.io](../../docs/architecture/refund-recovery.drawio).
The published study animates connectors with pause/resume and reduced-motion support.
Motion illustrates direction only.

## Reading the outcome chart

The study uses readable labels; the evidence retains its original arm identifiers.

| Study label | Recorded arm |
|---|---|
| Random policy search | `random_search` |
| Adaptive policy search | `recursive_optimizer` |
| Unchanged policy | `fixed_agent` |
| Fixed-rule tuning | `fixed_optimizer` |

Each arm has 132,840 final executions: the same 4,428 cases reused for 30 search
seeds. These are not 132,840 independent cases. The chart is computed directly
from the sealed report:

- **Completed** = `business_completed`.
- **Correct handoff** = `task_success − business_completed`. This final set requires
  no clarification, and all arms have zero false completions and unsafe effects.
- **Unresolved** = `episodes − task_success`.

| Approach | Completed | Correct handoff | Unresolved |
|---|---:|---:|---:|
| Random policy search | 92,684 | 3,960 | 36,196 |
| Adaptive policy search | 83,748 | 3,888 | 45,204 |
| Unchanged policy | 0 | 1,800 | 131,040 |
| Fixed-rule tuning | 0 | 3,960 | 128,880 |

Correct handoff is narrower than human intervention. Many interventions fail a
case that requires completion. Rounded percentages may not sum to exactly 100%.

## Coverage

| Partition | Composition families | Cases |
|---|---:|---:|
| Development | 1,187 | 1,187 |
| Validation | 556 | 556 |
| Final test | 1,107 | 4,428 |
| Total | 2,850 | 6,171 |

The final corpus has 3.65 times as many cases as v2. All 636 previously exposed v2
families stay in development. New families are grouped by complete fault/proposal
composition before partitioning; all four final parameter variants stay together.

New behavior includes:

- temporary and permanent outages at cancellation, refund and access stages;
- repeated ambiguous responses before and after commit;
- delayed or persistently unavailable receipt lookup, while exact retry remains possible;
- paired and three-stage interruptions;
- consent revocation or expiry after earlier changes have committed;
- version conflicts between a read and a later write;
- date, amount and resource proposal errors combined with those conditions.

Unreachable downstream variations after a permanent failure are normalized away.
The generator constructs expected state directly, without running a candidate.
Correct handling distinguishes completion from truthful handoff with the correct
committed prefix. Transient cases exceeding the retry cap and unsupported
stale-version recovery remain in the denominator.

The shared simulator and authored compositions are limitations. More synthetic
cases do not establish production readiness or independent external validity.
Parameter variants and repeated seeds are correlated.

## Reproduce

From the source checkout, with the committed uv lockfile:

```bash
uv sync --locked
uv run --locked python -m benchmarks.recursive_improvement_v3 validate

uv run --locked python -m benchmarks.recursive_improvement_v3 search \
  --out-dir reports/new-v3-search

uv run --locked python -m benchmarks.recursive_improvement_v3 evaluate \
  --search-dir reports/new-v3-search --out-dir reports/new-v3-final

uv run --locked python -m benchmarks.recursive_improvement_v3 audit \
  reports/new-v3-final
```

Use fresh output directories. Search consumes development/validation only;
the separate evaluation verifies the committed selection before loading final
cases. Exit 0 means the experiment completed, including negative/null outcomes.
Exit 2 indicates an integrity or configuration error. Nothing is deployed.

## Evidence and comparison

Read the [recorded results](recordings/README.md) and [frozen protocol](PROTOCOL.md).
The four arms use the same 30 paired seeds, eight generations, two proposals per
generation, 17 development queries and 17 validation queries per arm/seed.
The original fixed heuristic remains intentionally unchanged, including its known
credit-assignment weakness. The primary registered comparison is recursive versus
uniform random search, with comparisons against the fixed heuristic secondary.

Reports include overall and category results, business completion, intervention,
unsafe effects, duplicate refunds, false completion, provider calls, and paired
seed intervals. These intervals are conditional on the fixed synthetic corpus.
The aggregate follows the authored family distribution, not production traffic.
The same v2 hand-written reference is evaluated outside the search allowance.

The provider advances deterministic schedules per call; it does not simulate
network latency, backoff, parallel requests or failure probabilities. Equal query
allowances do not imply equal CPU time, model tokens or cost.

Every compressed batch contains per-case counts and full trace hashes.
Exact selected configurations are exported. To reconstruct one trace:

```bash
uv run --locked python -m benchmarks.recursive_improvement_v3 inspect \
  reports/new-v3-final \
  --batch BATCH_SHA256 --case CASE_ID --out reports/new-v3-trace.json
```

Inspection verifies the original trace commitment. Audit reconstructs search,
selection, distinct policy/case execution, category slices and registered
comparisons. Hashes identify content; they are not external attestations.

The standalone HTML report includes the animated improvement loop, keyboard
pause/resume, reduced-motion support and a selected-configuration viewer. Static
tables and charts remain available without JavaScript. Motion is illustrative.

V1 and v2 evidence is retained unchanged. V2/v3 score differences are not a pure
sample-size effect because provider behavior and corpus composition changed.
Original code and all new synthetic cases use MIT-0.

## Original run verification

Verified locally on 29 October 2026, before the presentation redesign:

- 273 repository tests passed, including 35 v3 checks.
- All 636 legacy families retained baseline and reference outcomes under the
  extended simulator.
- Full audit reconstructed search, selection, all 264,744 distinct policy/case
  executions, category slices and registered comparisons. Exported configurations
  matched their selected identities.
- The static build produced 82 HTML pages and 676 files; internal links and
  anchors resolved.
- Chromium verified selected-proposal navigation, moving connectors, keyboard
  pause/resume, reduced motion, mobile layout, print, no-JavaScript fallback and
  absence of external requests. Desktop and mobile screenshots were inspected.
- Gitleaks reported no findings in the new source/recordings or in a separate
  scan of all 214 decompressed evidence batches.
