# A broader test of bounded recursive improvement

This revision expands the subscription recovery experiment to **636 distinct
semantic fault-combination families** and **30 paired search seeds**. It also fixes
v1's incumbent-only validation: every proposed policy can now be considered after
search, including proposals rejected by the development selection rule.

This is synthetic, finite configuration search with no model calls or training.
The original [v1 implementation and negative result](../recursive_improvement/README.md)
are preserved. Original code and synthetic data use MIT-0.

## Coverage

| Partition | Composition families | Cases |
|---|---:|---:|
| Development | 180 | 360 |
| Validation | 153 | 306 |
| Final test | 303 | 1,212 |

Cases cover renewal cancellation, immediate cancellation, refunds, unknown
outcomes, zero through four transient access failures, persistent outages,
combinations of scoped proposal mistakes, and fourteen authority/race conditions.
The 31 normalized families exposed in v1 are development-only.

Variants stay within their semantic family's partition. New identifiers and
financial values are not counted as new families. Terminal authority cases are
not multiplied by unreachable provider-fault schedules to inflate coverage.

The author, simulator and primitive fault vocabulary remain shared. These are
distinct authored compositions, not independent enterprise samples or independently
authored test suites. The final set is public and author-visible.

## What changed in selection

In v1, a three-retry policy could handle all development cases but cost slightly
more than a one-retry policy. Development rejected it, and validation could not
recover it because validation saw only incumbents.

V2 broadens development coverage across outage depths and saves every proposal.
After search ends, validation scores the complete proposal archive. The best
eligible proposal preserving baseline validation successes is selected and committed
before final testing. Validation feedback never reaches the optimizer.

Both coverage and selection changed. Score changes from v1 cannot be attributed
to sample size alone.

## Comparison

All four arms use the same starting workflow, eight generations and two proposals
per generation:

1. **Fixed agent:** repeat the starting policy.
2. **Random search:** sample uniformly from the complete 96-policy space.
3. **Fixed optimizer:** use the original fixed diagnostic proposal strategy.
4. **Recursive optimizer:** allow edits to failure attribution, ordering and edit
   width, and inherit accepted edits in subsequent generations.

Each seed and arm receives 17 development and 17 validation requests. Repeated
policies consume their allowance. Identical evaluations are cached because these
policies and providers are deterministic. Logical requests and physical executions
are reported separately; there is no equal-CPU-time or model-token claim.

The recursive mechanism is unchanged from v1. It scores optimizer edits by their
immediate development effects; it does not independently measure their long-term
value. The outer search, mutation language, guard and grader stay fixed.

A predeclared hand-written reference policy is evaluated separately. It provides
an engineering comparison outside the matched optimization budget. It is not an
exhaustive oracle. Four-failure cases exceed the language's maximum three retries
and remain in the denominator.

## Reproduce

From the source checkout:

```bash
uv sync --locked
uv run --locked python -m benchmarks.recursive_improvement_v2 validate

uv run --locked python -m benchmarks.recursive_improvement_v2 search \
  --out-dir reports/rsi-v2-search

uv run --locked python -m benchmarks.recursive_improvement_v2 evaluate \
  --search-dir reports/rsi-v2-search --out-dir reports/rsi-v2-final

uv run --locked python -m benchmarks.recursive_improvement_v2 audit \
  reports/rsi-v2-final
```

Use new output paths for each run; evidence is never overwritten. Exit 0 means
a valid experiment completed, including null/negative outcomes. Exit 2 indicates
configuration or integrity failure. No command deploys a candidate.

Read the [recorded comparison](recordings/README.md) and [frozen protocol](PROTOCOL.md).
The standalone HTML report contains moving connectors, keyboard pause/resume,
reduced-motion support, a generation viewer and the actual validation-selected
proposal. Tables and charts remain readable without JavaScript.

## Evidence and inspection

The output directory includes:

- `comparison.json`: complete proposal histories, selected artifact identities,
  comparisons, seed-level uncertainty and references to evidence batches.
- `comparison.html` and `comparison.md`: interactive and static summaries.
- `batches/<sha256>.json.gz`: deduplicated deterministic policy evaluations. Every
  case retains its counts and the hash of its full timing-free action/effect trace.
- `candidates/<sha256>.json`: exact selected configurations.

Audit reconstructs search and selection, executes distinct policy/case combinations,
and recomputes outcomes, comparisons and bootstrap intervals. It verifies the
compressed evidence files rather than trusting aggregate scores.

To inspect a full trace, choose a batch hash and a case ID from an evidence batch:

```bash
uv run --locked python -m benchmarks.recursive_improvement_v2 inspect \
  reports/rsi-v2-final \
  --batch BATCH_SHA256 --case CASE_ID --out reports/rsi-v2-trace.json
```

Inspection reconstructs the trace and checks it against its recorded hash.
Hashes identify content; they are not authenticated attestations.

## Statistical interpretation

Report paired differences across the 30 search seeds. The percentile bootstrap
resamples entire paired seeds, keeping each arm's result on the same seed together.
The 95% interval is conditional on this fixed synthetic corpus; it does not describe
production uncertainty or independently sampled scenario families.

Four variants within each family and repeated runs on the same test are correlated.
The experiment has 1,212 final cases in 303 composition families, regardless of how
many selected policies execute them. Logical execution counts must not be presented
as independent-case counts.

The common invariant guard protects all arms. Zero unsafe effects do not mean the
optimizer learned authorization. All cases are invented; no customer, employer or
production material is included. No external project runtime is called.

## Verification record

Verified locally on 29 October 2026:

- 238 repository tests passed, including 31 new v2 checks.
- Full search/selection replay and all 83,328 distinct policy/case executions
  matched the recorded evidence and registered comparisons.
- Exported selected configurations matched their committed identities.
- The static build produced 78 HTML pages and 423 files; internal links and anchors
  resolved.
- Chromium checked selected-proposal navigation, generation navigation, actual
  moving connectors, keyboard pause/resume, reduced motion, mobile overflow,
  printing, no-JavaScript fallback and absence of external requests. Desktop and
  mobile screenshots were inspected.
- Gitleaks reported no findings in the new experiment source/recordings or in a
  separate scan of all decompressed evidence batches.
