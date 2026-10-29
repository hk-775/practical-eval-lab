# Bounded RSI v3: failures across workflow stages

Synthetic serial subscription workflows; finite configuration search, no LLM or production provider. New stage outages, repeated ambiguous responses, delayed receipts and temporal authority/CAS races extend the shared simulator. All v2 families are development-only. Search rules, policy space, seeds and query budgets are unchanged from v2. Parameter variants and repeated seeds are correlated; intervals quantify search-seed variation on this fixed corpus.

## Main comparison

Recursive minus random search: -6.78 percentage points; 95% paired-seed interval -15.33 to +0.94 percentage points. No clear advantage over random search is established.

## Corpus

| Partition | Composition families | Cases |
|---|---:|---:|
| Development | 1,187 | 1,187 |
| Validation | 556 | 556 |
| Test | 1,107 | 4,428 |

All 636 previously exposed v2 families are development-only. The final test
contains new combinations of stage outages, repeated ambiguous responses, delayed
receipts, interruptions across stages, authority withdrawal and version races.
Four parameter variants remain together in each final family. The author, business
rules and simulator primitives are shared; this is not an independent enterprise sample.

## Final results

| Arm | Correct handling | Business completion | Human intervention | Unsafe effects | Provider calls / case |
|---|---:|---:|---:|---:|---:|
| Fixed agent | 1.36% | 0.00% | 100.00% | 0 | 2.35 |
| Random search | 72.75% | 69.77% | 30.23% | 0 | 11.60 |
| Fixed optimizer | 2.98% | 0.00% | 100.00% | 0 | 5.39 |
| Recursive optimizer | 65.97% | 63.04% | 36.96% | 0 | 10.86 |

Correct handling includes required clarification and truthful handoff with the
correct committed prefix. Permanent outages and withdrawn authority remain in the
business-completion denominator. All arms use the same fixed authorization guard.
Across the four arms: 0 duplicate refund effects, 0 false completions and 0 candidate errors.

## Correct handling by failure class

| Failure class | Final cases | Fixed agent | Random search | Fixed optimizer | Recursive optimizer |
|---|---:|---:|---:|---:|---:|
| Delayed Receipt | 1,404 | 0.00% | 74.49% | 0.00% | 65.08% |
| Late Authority | 72 | 27.78% | 100.00% | 100.00% | 97.59% |
| Multi Stage | 1,008 | 0.00% | 73.61% | 0.00% | 67.90% |
| Repeated Unknown | 936 | 0.00% | 62.05% | 0.00% | 54.80% |
| Stage Outage | 616 | 6.49% | 68.31% | 9.74% | 66.39% |
| Stage Timeout | 360 | 0.00% | 100.00% | 0.00% | 91.93% |
| Stale Version Race | 32 | 0.00% | 0.00% | 0.00% | 0.00% |

The aggregate follows the authored composition distribution, not production traffic.
Small temporal slices should be read with their denominators, not treated as precise estimates.
The unchanged hand-written v2 reference handled 3,288/4,428 cases correctly (74.25%); it is outside the search budget.

## Registered paired comparisons

| Comparison | Mean difference | 95% paired-seed interval | Wins / ties / losses |
|---|---:|---|---:|
| Recursive optimizer vs Random search | -6.78 pp | -15.33 to +0.94 percentage points | 9 / 8 / 13 |
| Recursive optimizer vs Fixed optimizer | +62.99 pp | +55.66 to +69.52 percentage points | 30 / 0 / 0 |
| Random search vs Fixed optimizer | +69.77 pp | +66.34 to +73.07 percentage points | 30 / 0 / 0 |

Recursive versus random was registered before this run. The fixed diagnostic
optimizer retains its known tendency to revisit scope errors repaired earlier in a
failed episode. A large margin over that heuristic alone does not establish an RSI advantage.

Intervals use 10,000 bootstrap resamples of entire paired search seeds. They are
unadjusted descriptive intervals conditional on this fixed corpus, not production
or independent-family confidence intervals. Repeated seeds and variants are correlated.

## Work and evidence

- 30 paired seeds; eight generations; two proposals per generation.
- Each arm/seed receives 17 development queries and 17 validation queries.
- All proposals reach validation after search; selected identities are committed before final testing.
- Logical development/validation episodes: 3,555,720.
- Logical final episodes: 531,360.
- Physically executed distinct policy/case pairs: 264,744.
- Cache hits consume the same query allowance. CPU time, tokens and monetary cost are not matched.
- The policy language, optimizers, search rules, seeds and budgets are unchanged from v2.
- The corpus and provider behaviors changed; score differences are not a pure sample-size effect.
- Transient faults beyond the retry cap and unsupported stale-version recovery remain in the denominator.
- No language model, production provider, customer data or real money was used.
- Simulated schedules advance per call. Provider latency, backoff and concurrent races are not measured.

## Integrity

- Recorded UTC: `2026-10-29T15:35:09.289859+00:00`
- Protocol SHA-256: `2d78aa252ed6aef2db1d7e41d01684b6353543ccd05809fa88520312d1f09a28`
- Report SHA-256: `9a727365fd42f7c8ac528a19d46e5f5378616ee8cead14b0ad665d92e82eddb9`
- Selected-set SHA-256: `715e86a84281ff8b417481c1e28f4eda546c17c05539be0e8356966c3c7849bf`
- Source revision: `8339007f7c0cc2fca03ed5e68581e64a4762c0ba`; working tree dirty: `True`.

Compressed evidence retains each case's outcome and complete trace commitment.
`inspect` reconstructs a full trace. `audit` replays search, selection, execution,
category slices and comparisons. Hashes identify content; they are not signed attestations.
No candidate is deployed. Original code and synthetic cases: MIT-0.
