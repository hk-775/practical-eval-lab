# Bounded RSI v3: failures across workflow stages

## Engineering question

With the v2 policy language, optimizers, selection rule, seeds and query allowances
unchanged, how reliably do the selected workflows complete or safely hand off
when interruptions occur at different stages and authority changes during execution?
Does recursive search outperform uniform random search as well as the fixed heuristic?

This is a synthetic serial simulator and finite configuration search. It does not
test a language model, model weights, real subscriptions, distributed concurrency
or a deployed gateway. The v1 and v2 source, datasets and evidence remain frozen.

## Corpus design

Canonicalize the 636 exposed v2 composition families into stage schedules and keep
all of them in development. Deduplicate new schedules against those families.
New coverage includes:

- one, two, three or four transient failures and persistent unavailability at
  cancellation, refund and access stages;
- one, two or four ambiguous responses before or after commit at each stage;
- receipts that are immediately visible, hidden for two lookups, or persistently
  absent from the lookup endpoint while exact retry can still return the receipt;
- four declared paired-stage schedules and four three-stage interruption schedules;
- revocation, expiry and compare-and-swap version races immediately before later
  workflow steps, after earlier steps may have committed;
- applicable date, amount and resource proposal errors combined with those faults.

Do not multiply a permanent early failure by unreachable downstream faults or
proposal mistakes. Before-commit timeouts have no receipt-delay variants because
no receipt exists. For temporal cases only vary proposals before the event.
Canonical composition hashes are the split unit. Within category/intent strata,
sort new families by the declared salted hash and assign approximately 25% to
development, 25% to validation and 50% to final testing. Small strata retain at
least one family per partition. All four final parameter variants stay together.
The manifest supplies exact counts, category counts and hashes of declarations
and generated cases.

Expected business state is constructed directly from the instruction and fault
schedule, without executing a candidate or querying the guard. Transient failures
and version conflicts retain a completion target, including cases beyond the
policy language's capabilities. Permanent provider failure or withdrawn authority
requires truthful handoff with the correct committed prefix. Successful handoff
does not count as business completion.

The corpus is author-visible, public and synthetic. Shared primitives and authored
compositions are not independent enterprise samples. Four variants per family and
multiple search seeds do not multiply the number of independent scenarios.

## Provider and grading

Extend the original simulator in a new module; do not change its frozen kernel.
Keep the original mutation guard and idempotency semantics. A scheduled authority
or version event occurs before the first attempted write at that stage. Invalid
or unauthorized proposals cannot consume a fault to bypass the guard.

Unavailable responses and before-commit ambiguity occur before a permitted new
write. After-commit ambiguity can mask either a new receipt or an exact duplicate
response. Exact retries use the same payload and key. A receipt visibility delay
affects lookup only; it does not discard the committed mutation or idempotency
record. Schedules advance per eligible call, not wall time. No real retry latency,
backoff, rate limiting, failure probability or provider SLA is modeled.

Retain independent expected-effect grading and compare final business records.
Also capture trusted authority state at every committed effect and independently
reject writes after revocation/expiry or outside current authority. Earlier valid
commits remain valid after a later withdrawal. Report unsafe effects, duplicate
refunds, false completion, task handling, business completion, intervention and
provider calls. All arms share the guard; zero unsafe effects are not learned safety.

## Search and comparisons

Reuse v2 `search_arm` unchanged: fixed agent, uniform random search, fixed optimizer
and recursive optimizer; the same 30 paired seeds; eight generations and two
proposals each; 17 development queries and 17 validation queries per arm/seed.
All 17 proposals reach validation after development search ends. Selection is
committed before the separate final-test command. No validation or final feedback
enters proposal generation. Keep the same 96 policies and 12 optimizer settings.
The existing `access_retries` setting handles unavailable responses at every stage;
its historical name and behavior remain unchanged.

The fixed optimizer's known tendency to revisit repaired scope errors remains a
limitation of this comparator. Prespecify recursive versus random as the primary
descriptive comparison, and recursive/random versus fixed as secondary comparisons.
For each, report paired seed differences, wins/ties/losses and reproducible
10,000-resample percentile intervals. These are unadjusted descriptive intervals
conditional on this corpus, not multiplicity-controlled hypothesis tests,
independent-family intervals or production confidence claims.

Report category slices with explicit denominators to expose rare failure classes.
The aggregate follows the authored composition distribution, not a production
traffic mix. Evaluate the unchanged v2 hand-written reference after selection,
outside the matched search allowance; it is neither an oracle nor trained.

Cache exact policy/split executions while charging every logical query. Report
physical executions and logical requests separately; this does not match CPU
time, tokens or monetary cost. Do not interpret v2/v3 score differences as a pure
sample-size effect: the corpus and provider behaviors have changed.

## Evidence

Freeze this protocol, provider, data generator, search integration, inherited
kernel fingerprints, default plan and reference before recorded search. Load only
development/validation during search. Reconstruct and verify search and selection
before loading final cases. Retain every seed and all negative/null results.

Content-addressed compressed batches retain case outcomes, category, policy and
full timing-free trace hashes. Development batches retain the public feedback
consumed by the optimizer. `inspect` reconstructs one complete trace and checks its
commitment. `audit` reconstructs search, selection, case execution, category slices
and all registered comparisons, and verifies exported selected configurations.
Timing and source-environment metadata are outside deterministic replay equality.
Content hashes are not external attestations. No command deploys a candidate.

All data is invented and contains no customer, employer or proprietary material.
Original code and synthetic cases use MIT-0.
