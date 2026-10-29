# Bounded recursive improvement protocol v1

## Engineering question

Under the same candidate-evaluation allowance, does evolving a recovery agent's
proposal strategy improve its final task handling compared with a fixed proposal
strategy? The task is a confirmed subscription change across billing and access,
including ambiguous provider timeouts, proposal mistakes, and access outages.

This is finite, local program/configuration search. No language model is called,
no model weights are trained, and no production workflow is modified.
The experiment can falsify an advantage for the recursive arm.

## Three paired arms

Each seed starts with the same workflow and the same optimizer configuration:

1. **Fixed agent:** repeat the starting workflow without editing it.
2. **Fixed optimizer:** mutate the workflow using a fixed trace-attribution,
   field-ordering, and edit-width strategy.
3. **Recursive optimizer:** one proposal per generation uses the inherited
   optimizer; the other changes one optimizer field and uses that changed
   optimizer to generate a workflow proposal. An accepted optimizer becomes the
   parent for subsequent generations.

The third arm co-evolves an agent and a small optimizer configuration. Its outer
interpreter, mutation vocabulary, acceptance rule, and experiment budget are
human-authored and fixed. This is a bounded model of recursive improvement, not
unrestricted source-code self-modification or a claim of accelerating intelligence.
The fixed optimizer already uses all observed failure signals; it is not restricted
to looking at the last error. It has a one-field edit width. Width two is in the
recursive search space. Any advantage is relative to this specified baseline.

Default plan: seeds 11, 29, 47, 71, 101; eight generations; two proposals per
generation; maximum 32 steps per episode. Every arm receives exactly 17 development
candidate evaluations and nine validation candidate evaluations per seed. Repeated
artifacts are re-executed and consume their allowance. There are no free
look-aheads or unreported attempts. Actual simulated provider-call counts are
reported. Equal evaluation allowances are not equal CPU time, token usage, or money.

## Editable and protected state

An artifact is a strict JSON object with a version, five workflow fields, and three
optimizer fields. Extra keys, unsupported values, booleans in integer slots, and
duplicate JSON keys are rejected. The configuration language cannot express
imports, paths, shell commands, network calls, or arbitrary code.

Workflow fields: handling unknown outcomes, handling missing receipts, access
retry count, repairing scoped collaborator proposals, and asking for missing dates.
Optimizer fields: attributing the last or all observed failure signals, ordering
the fields by frequency/rarity/randomness, and changing one or two workflow fields.

The fixed interpreter verifies receipt payloads, preserves retry identity, and
checks final state before claiming completion. Every mutation goes through the
unchanged subscription invariant guard. Grading is performed by the separate,
unchanged effect/final-state checker. All original subscription protocol hashes
and frozen evidence remain intact.

This is a capability-limited configuration interpreter in a trusted Python process.
It is not an operating-system sandbox for arbitrary third-party Python. No plug-in
imports or external code adapters are accepted by this experiment.

## Development, selection, and final test

Partitions contain 24 development, 18 validation, and 24 test episodes. Each family
has two financial/date/identifier variants. Each partition uses distinct authored
fault compositions: development introduces individual failures, validation combines
them, and test uses different combinations and deeper temporary outages. Declared
compositions, family names, and subscription identifiers are checked for overlap.

Cases and expected state are authored before optimization. Expected state is not
produced by running a candidate or calling the guard. Candidate observations omit
references, fault schedules, condition labels, case IDs, and split names.
Optimizer feedback contains only development success bits and public tool statuses
and reasons. It receives no reference state or validation/test traces.

Partitions share an author, provider simulator, fault vocabulary, and business
rules. They are composition-disjoint synthetic families, not independent customer
samples or independently authored benchmark datasets. The test is author-visible
and public once the source is shared. It cannot remain a blind benchmark after
results or cases have been inspected.

Freeze the kernel, datasets, and default plan before the recorded search.
`search` evaluates development candidates, completes all generations, then scores
the incumbent checkpoints on validation. Validation feedback never enters the
optimizer. The earliest checkpoint with the best eligible validation score is
selected. Hash all selected artifacts before starting the separate `evaluate`
command. That command verifies selection by replay before loading the test.

Do not tune against final results and keep describing the same test as untouched.
If a kernel defect is found after recording, retain the old evidence and introduce
an explicitly corrected protocol version. Reproduction and audit reruns do not
constitute new independent evidence.

## Acceptance and measurements

A development candidate must preserve every previously successful development
episode and strictly improve the lexicographic rank: safety/execution eligibility,
correct task handling, legitimate completion, then fewer simulated provider calls.
Eligibility requires zero observed unsafe effects, duplicate refunds, false
completion claims, and candidate errors. Neutral changes do not enter the lineage.
Validation selection preserves the baseline's successful validation episodes.

Report correct task handling, completed legitimate changes, recovery, appropriate
abstention, intervention demand, unsafe effects, duplicate refunds, false completion,
provider calls, and accepted optimizer changes. Final results include every selected
arm and seed, including failures. Include paired per-seed differences between
recursive and fixed optimizers. Variants and repeated seeds are correlated;
no binomial confidence intervals or production failure rates are inferred.

Correct handoff during persistent provider failure counts as correct task handling,
but the business change remains incomplete. Denying all changes cannot satisfy
legitimate completion. A zero unsafe-effect count under the common invariant guard
is evidence about this combined simulation, not learned authorization or a guarantee.

Final test gates mark versioned artifacts eligible for human review when they
improve baseline task handling, preserve its successful cases, and pass the observed
safety/execution checks. This does not deploy or certify the candidate.
No final test feedback is sent back to optimization.

## Evidence

Store the complete search plan, every proposed configuration, diagnosis, change,
score, accepted parent/child lineage, checkpoint validation result, and selection
commitment. Store final tool calls, responses, effects, and independent grading.
Content hashes identify the kernel, original subscription kernel, datasets,
artifacts, selected set, search, and report.

Audit reconstructs the deterministic search and selection; regenerates actions
from the selected policy; replays recorded actions against the provider; and
recalculates metrics and review flags. Timestamps and local wall times are not
deterministic outputs. Hashes are integrity checks, not authenticated attestations.

The report must identify bounded configuration evolution, synthetic data, shared
guard, actual evaluation allowance, test exposure, and any absent recursive
advantage. Preserve null and negative results.
