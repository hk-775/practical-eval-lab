# Recorded bounded RSI experiment

Recorded on **29 October 2026 UTC**. This is original MIT-0 synthetic evidence
from a finite configuration-search experiment. No language model, production
provider or external project runtime was invoked.

- [Interactive report](2026-10-29/comparison.html)
- [Complete JSON evidence](2026-10-29/comparison.json)
- [Static Markdown summary](2026-10-29/comparison.md)
- [Protocol](../PROTOCOL.md)
- [Run and adapt the experiment](../README.md)

## Result

| Arm | Correct handling | Legitimate completion | Unsafe episodes | Duplicate refunds |
|---|---:|---:|---:|---:|
| Fixed agent | 30/120 | 0/80 | 0/120 | 0 |
| Fixed optimizer | 104/120 | 44/80 | 0/120 | 0 |
| Recursive optimizer | 92/120 | 32/80 | 0/120 | 0 |

**The recursive optimizer did not outperform the fixed optimizer in aggregate.**
On correct handling it won one, tied two, and lost two of five paired seeds.
Both search methods improved on the starting workflow. Keep this negative
comparison result when presenting the experiment.

The recursive arm's only winning seed, 101, accepted no optimizer changes.
That win therefore does not establish a benefit from inherited optimizer edits.
The full proposal history is necessary to interpret the aggregate comparison.

Each arm used 24 final episodes across five seeds: the 120 outcomes are repeated
trials on the same 12 synthetic families, not 120 independent enterprise cases.
Correct handling includes required clarification and truthful handoff.
Permanent provider outages remain in the legitimate-completion denominator.
The common invariant guard protected every arm; these zero-violation counts do
not demonstrate learned authorization.

## What was frozen and executed

The default plan used eight generations and two trials per generation.
Each arm and seed consumed exactly 17 development candidate evaluations
(408 episodes) and nine validation candidate evaluations (162 episodes).
Across all arms and seeds, the recorded search executed 8,550 development/validation
episodes. Search replay and audit executions are additional verification work,
not extra optimization attempts.

Optimizer configuration changes were accepted during the recursive search.
The exact changes, parent/child identities, strategy actually used, and subsequent
proposals are recorded. An accepted edit later in a run may not appear in the
earlier checkpoint selected by validation.

The selected artifact set was committed by content hash before final evaluation.
The final result includes every arm and seed. The test is public, author-visible,
and shares a provider model, author and fault vocabulary with development.
It must not be reused for tuning while being described as untouched.

## Inspect a selected candidate

For seed 11, the recursive arm's selected configuration and change description are:

- [Selected configuration](2026-10-29/candidates/11-recursive_optimizer.json)
- [Changes from the starting configuration](2026-10-29/candidates/11-recursive_optimizer.changes.json)

All 15 selected configurations and their change descriptions are stored in the
same `candidates/` directory. They are reviewable artifacts; none was deployed.

## Audit

From the repository root:

```bash
uv sync --locked
uv run --locked python -m benchmarks.recursive_improvement validate
uv run --locked python -m benchmarks.recursive_improvement audit \
  benchmarks/recursive_improvement/recordings/2026-10-29/comparison.json
```

The audit reconstructs the complete deterministic search and selection, regenerates
actions from selected policies, replays all **360 final episodes**, and recalculates
effects, metrics, comparisons and review flags.

- Protocol SHA-256: `d544ccc766f8f2e94120148731882a71586e0ac1e51ac267044c959e47f33895`
- Search SHA-256: `5f128c5e80c2a58a50260eab76858a0e2b1f7eccc77329c9c526f847f8cf4827`
- Selected-set SHA-256: `bef2d18838cc467318a57565abf7509de33e2bee69c25b3967b5a9c02ec5499b`
- Report SHA-256: `4743659dc66a49b6c96b100f24c013070172a4eda6c657aaf5f51675c0f0dad8`

The recorded Git revision precedes uncommitted experiment work; the report
explicitly records `worktree_dirty: true`. The protocol and content hashes identify
the actual executed implementation. They are integrity checks, not signatures.
