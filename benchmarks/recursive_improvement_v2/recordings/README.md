# Expanded RSI results: 29 October 2026

- [Interactive report](2026-10-29/comparison.html)
- [Complete search and comparison JSON](2026-10-29/comparison.json)
- [Static summary](2026-10-29/comparison.md)
- [Exploratory recursive-versus-random diagnostic](2026-10-29/diagnostics.json)
- [Protocol](../PROTOCOL.md) and [reproduction instructions](../README.md)

The fixed final corpus contains **1,212 scenarios across 303 distinct composition
families**. Four parameter variants stay within each family. Four search arms were
evaluated across **30 paired seeds**, using the same evaluation-request allowance.

## Final correct handling

| Arm | Mean correct handling |
|---|---:|
| Fixed agent | 8.25% |
| Random search | 80.79% |
| Fixed diagnostic optimizer | 23.43% |
| Recursive optimizer | 82.90% |
| Predeclared hand-written reference, outside the search budget | 86.80% |

All arms recorded zero unsafe effects and duplicate refunds under the common
invariant guard. This is not learned authorization. Correct handling includes
required clarification and truthful handoff; business completion is reported
separately. Four-failure scenarios exceed the policy language's three-retry limit.

## What this establishes

The recursive arm exceeded the fixed optimizer on every paired seed. Its mean
advantage was 59.47 percentage points, with a paired-seed percentile bootstrap
interval of +55.87 to +62.21 points.

The **fixed heuristic has an attribution weakness**: it counts scope errors in a
failed episode even when the workflow already repaired them before a later failure.
After its first useful change, the most frequent signal continues to be scope
repair. It repeatedly proposes disabling that repair; those proposals are rejected.
The full search histories retain these attempts.

Random search performs much better than that heuristic. In an explicitly
**post-hoc exploratory comparison**, recursive search exceeded random search by
2.11 percentage points, with a paired-seed interval of **−2.31 to +6.25 points**.
It won 13, tied 10 and lost 7 paired seeds. This run does not establish a clear
advantage over random search.

Intervals describe variation across search seeds conditional on this fixed
synthetic corpus. They do not quantify production uncertainty or independently
sampled scenario-family uncertainty. The additional comparison was computed after
inspecting results; it is not part of the preregistered primary comparison.

V2 changes both scenario coverage and candidate selection. Its scores cannot
isolate the effect of a larger sample size, and they should not be compared with
v1 as if the benchmark were otherwise unchanged.

## Work and replay

The default search used 1,358,640 logical development/validation episodes.
Repeated deterministic policies consume their logical allowance and reuse cached
execution. Final outcomes cover 120 selected arm/seed pairs, representing 145,440
logical final episodes on the same 1,212 cases.

There were **83,328 distinct policy/case executions** across search, validation,
final evaluation and the reference. Additional audit work is separate.
Evidence is deduplicated into 208 compressed batches. Every case retains its
counts and complete timing-free trace hash.

```bash
uv run --locked python -m benchmarks.recursive_improvement_v2 audit \
  benchmarks/recursive_improvement_v2/recordings/2026-10-29
```

Audit reconstructs search and selection, regenerates distinct policy/case outcomes,
verifies the evidence batches and recomputes the registered comparisons. The
separate `diagnostics.py` reproduces the explicitly post-hoc comparison.

- Protocol SHA-256: `78dc2c1bb337f413f6e5add6933962ca5ce1eed5f8be1324f6360a368c19c855`
- Search SHA-256: `3af328f1fba6f699a7b0c2cfc105906dbf494f66a3052dbf737c0b37c65c9abc`
- Report SHA-256: `6b1b1b870ea7c018c1a796ccd52227718307cf36254dd156d7b730d0693ce1ff`

The report records the actual source revision and a dirty working tree. Content
hashes identify the executed kernel; they are not signed attestations.

The cases are invented, public and author-visible. No customer, employer or
production data was used. No model was called or trained, and nothing was deployed.
