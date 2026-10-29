# Expanded bounded RSI evaluation

Synthetic finite configuration search with no LLM calls or production integrations. Variants stay within composition families; v1-exposed families are development-only. All arms share an invariant guard and deterministic provider. Evaluation requests consume equal allowances, including cache hits. Physical cached execution differs from logical evaluation work. Seed uncertainty is conditional on this authored, public synthetic corpus.

Recursive versus fixed optimizer: +59.47 percentage points in mean final correct handling. Across 30 paired seeds: 30 wins, 0 ties, 0 losses. 95% paired-seed bootstrap interval: +55.87 to +62.21 percentage points.

## Final results

| Arm | Correct handling | Business completion | Unsafe effects | Provider calls per case |
|---|---:|---:|---:|---:|
| Fixed agent | 8.25% | 0.00% | 0 | 2.69 |
| Random search | 80.79% | 63.13% | 0 | 11.75 |
| Fixed optimizer | 23.43% | 5.96% | 0 | 7.47 |
| Recursive optimizer | 82.90% | 64.92% | 0 | 11.86 |

Predeclared hand-written reference: 1052/1212 correctly handled (86.80%). It is outside the matched search budget.

## Exploratory comparison with random search

Recursive minus random: +2.11 percentage points.
Paired-seed 95% percentile interval: -2.31 to +6.25 percentage points.
This comparison was added after inspecting results. It is exploratory, not preregistered.
The fixed heuristic repeatedly targets previously repaired scope errors in compound
failure traces. Its low score is a limitation of this baseline; the larger margin
against it does not establish a general advantage for recursive improvement.

The fixed final corpus has 1,212 scenarios in 303 semantic composition families.
Four parameter variants per family and repeated seeds are correlated. Bootstrap
intervals resample paired search seeds only, conditional on this synthetic corpus.
They do not describe independently sampled enterprise or scenario-family uncertainty.

## Design

Development: 360 cases / 180 families. Validation: 306 cases / 153 families.
Previously exposed v1 families are development-only. All partitions include the
supported transient outage depths and persistent failures. Four-failure scenarios
exceed this policy language's three-retry limit and remain in the denominator.

Validation examines every proposal after search ends, including development-rejected
proposals. The selected set is committed before final cases are evaluated.

## Work and evidence

- Logical search requests: 4,080.
- Distinct policy/case executions in search: 63,936.
- Distinct policy/case executions including final and reference: 83,328.
- Cache hits spend the same logical allowance. These are not matched CPU-time or token budgets.
- The common fixed guard protects every arm; zero violations do not demonstrate learned authorization.
- Compact batches retain every case's counts and complete-trace hash. `inspect` reconstructs
  a full trace and verifies that commitment; `audit` reconstructs the whole experiment.
- Protocol SHA-256: `78dc2c1bb337f413f6e5add6933962ca5ce1eed5f8be1324f6360a368c19c855`
- Report SHA-256: `6b1b1b870ea7c018c1a796ccd52227718307cf36254dd156d7b730d0693ce1ff`
- Selected-set SHA-256: `80aa1ab0183dd021a0a20a86d9157f62e3f7c09188158041079039c09591926c`
- Recorded UTC: `2026-10-29T15:05:37.744281+00:00`
- Source revision: `f3774d865332bfaf107d686fd2e53a1cb4a34f3f`; dirty: `True`.

This revision changes both case coverage and candidate selection; score differences
from v1 cannot be attributed to sample size alone. No model was trained or invoked.
The author, provider model and fault vocabulary remain shared. No artifact is deployed.
