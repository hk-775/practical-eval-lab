# Recorded stage fault evaluation

Recorded locally on 29 October 2026. These are synthetic serial subscription
workflows and finite configuration searches, with no model calls, customer data
or production integration.

[Open the interactive report](2026-10-29/comparison.html) ·
[Read the static report](2026-10-29/comparison.md) ·
[Inspect the JSON evidence](2026-10-29/comparison.json)

## Results

The final corpus contains **4,428 cases in 1,107 new composition families**.
Thirty paired seeds reuse that same corpus. All 636 exposed v2 families remain
in development; v1 and v2 recordings are unchanged.

| Arm | Correct handling | Business completion | Human intervention |
|---|---:|---:|---:|
| Fixed agent | 1.36% | 0.00% | 100.00% |
| Fixed optimizer | 2.98% | 0.00% | 100.00% |
| Random search | 72.75% | 69.77% | 30.23% |
| Recursive optimizer | 65.97% | 63.04% | 36.96% |

Recursive minus random is **−6.78 percentage points**, with a 95% paired-seed
percentile interval of **−15.33 to +0.94 points**: nine wins, eight ties and
13 losses. This larger experiment does not establish an advantage for recursive
search over random search. The interval is conditional on the fixed synthetic
corpus, not a production or independent-family confidence interval.

All four arms recorded zero unsafe effects, duplicate refunds, false completions
and candidate errors under the shared invariant guard. That protection was not
learned. Correct handling includes required handoff with the correct committed
prefix; handoff is not business completion.

The unchanged hand-written reference handled 3,288/4,428 cases correctly
(74.25%), outside the matched search allowance.

## What the added variety exposed

All arms score zero on the 32 stale-version cases: the policy interpreter cannot
refresh state and retry a stale write. These are eight authored families, not
32 independent enterprise incidents. They remain in the denominator.

Recursive search also scores below random on delayed receipts (65.08% versus
74.49%) and repeated unknown outcomes (54.80% versus 62.05%). See the report for
all category denominators. These descriptive slices were specified before the
run; they are not traffic-weighted estimates or separate significance tests.

The fixed diagnostic optimizer retains its known tendency to revisit already
repaired scope errors. Its low score is a comparator limitation. Beating that
heuristic alone does not demonstrate a general recursive-improvement benefit.

## Reproducible evidence

- 3,555,720 logical development/validation episodes.
- 531,360 logical final episodes across selected arm/seed pairs.
- 264,744 distinct policy/case executions, deduplicated into 214 compressed batches.
- Exact selected configurations and complete search histories retained.
- Every case retains its outcome and a commitment to its complete action/effect trace.

The query allowance, policy language, search algorithms and seeds are unchanged
from v2. The corpus and provider behavior changed, so score differences are not
a pure sample-size effect. There was no post-test tuning or deployment.

Use the [reproduction and audit commands](../README.md) to run a fresh experiment
or verify this recording. Original code and synthetic cases use MIT-0.
