# Bounded recursive improvement v2: broader coverage

## Question and scope

Does an evolving proposal strategy improve workflow recovery or search progress
over a fixed optimizer under the same evaluation-request allowance? This version
addresses v1's small case set, narrow outage coverage and incumbent-only validation.
It changes both coverage and selection, so a v1-to-v2 score difference cannot be
attributed to sample size alone.

This remains finite, deterministic configuration search: 96 workflow policies and
12 optimizer configurations. No LLM, model training, production provider, customer
data or arbitrary source-code modification is involved. The original v1 source,
freeze and negative result are retained.

## Scenario design and split

Enumerate the full supported recovery factorial:

- renewal cancellation, immediate cancellation, and cancellation with refund;
- no refund timeout, timeout before commit, and timeout after commit where a refund exists;
- zero, one, two, three or four transient access failures, plus persistent failure;
- independent cancellation, refund and access proposal mistakes where applicable;
- date, amount and resource mistakes, including combinations across stages.

Add separately specified authority conditions: missing date, read-only actor,
foreign actor, revoked/expired/unconfirmed consent, consumed approval, mismatched
grant actor/tenant/resource, wrong request approval/operation and revocation/renewal
races. Do not multiply these terminal authority failures by unreachable fault
schedules merely to inflate the number of families.

There are 636 semantic composition families. The 31 normalized families exposed
in any v1 partition are assigned to development. Remaining families are deterministically
partitioned within intent/authority strata using the declared hash salt:

- development: 180 families, two variants each, 360 episodes;
- validation: 153 families, two variants each, 306 episodes;
- final test: 303 families, four variants each, 1,212 episodes.

Financial/date/identifier variants stay in their family's partition. No family
crosses partitions. Expected business state is directly constructed without running
a candidate or querying the guard. The manifest commits both declarations and
generated full-case hashes.

The author, simulator, business rules and primitive fault vocabulary are shared.
Composition separation is not independent authorship, a random enterprise sample
or assurance against simulator bias. The test is public and author-visible.
Four-failure cases exceed the policy language's maximum three retries; include
these capability-limit failures in the denominator instead of removing them.

## Arms and budgets

All arms start from the v1 baseline. Use 30 predetermined paired search seeds,
eight generations and two proposals per generation:

1. fixed agent;
2. uniform random sampling of the complete 96-policy space;
3. fixed diagnostic optimizer;
4. evolving optimizer, with one inherited-strategy proposal and one optimizer-edit
   proposal each generation.

The fixed and evolving proposal interpreters are reused unchanged from v1.
An optimizer edit is retained only with a workflow revision that preserves prior
development successes and strictly improves development rank. Rank orders observed
safety/execution eligibility, task success, legitimate completion, then fewer
provider calls. Optimizer edits are evaluated by immediate development outcomes;
this version does not independently estimate their long-term value.

Every generated proposal is retained in an archive, including proposals rejected
by the development incumbent rule. After search finishes, validation scores all
17 archive slots, including repeated artifacts. Select the earliest highest-ranked
eligible entry preserving baseline validation successes. No validation feedback
re-enters the optimizer. This corrects v1's inability to select a development-rejected
but more robust policy. A selected proposal need not have been an incumbent.

Each arm and seed receives 17 development queries and 17 validation queries.
With the default plan these are 1,358,640 logical development/validation episodes,
not that many independent cases or necessarily that many physical executions.
Final comparison contains 1,212 cases for each of 120 selected arm/seed pairs.

Identical policy evaluations are cached by partition and policy hash because the
provider and policies are deterministic. Each cache hit consumes the same logical
evaluation request and contributes its full simulated work. Report cache hits,
misses, logical episode counts and actual physical policy/case executions separately.
No CPU-time, token-cost or paid-model-efficiency claim follows from this allowance.
Caches are accessible only to the trusted runner; optimizers receive requested
development feedback, never the cache or held-out references.

## Additional reference and comparisons

Predeclare a hand-written reference policy: exact retry after an unknown outcome,
three access retries, scoped proposal correction and missing-date clarification.
Evaluate it after selection as an additional engineering reference, outside the
matched optimizer budget. It is not an exhaustive oracle or a learned result.

Report final correct handling, legitimate completion, recovery, intervention,
false completion, unsafe effects, duplicate refunds and provider calls. Report
per-seed results and development progress. The common invariant guard protects
all arms; zero violations are not evidence of learned authorization.

For random and recursive search versus the fixed optimizer, report paired per-seed
success-rate differences, wins/ties/losses, mean difference and a reproducible
10,000-resample percentile bootstrap interval when at least five seeds are present.
Resample entire paired seeds; never treat individual outcomes or the four variants
as independent Bernoulli trials. The interval describes seed variability conditional
on this fixed synthetic corpus. It is not a production confidence interval and
does not quantify uncertainty over independently sampled scenario families.

## Freeze, final evaluation and evidence

Freeze code, reference policy, dataset, default budget and seeds before the recorded
search. Search loads development and validation only. Commit selected artifact
identities before the separate final evaluation. Verification of search reconstructs
the entire deterministic process before loading final cases.

Preserve every selected arm and seed, including inferior results. Do not tune on
the final results while keeping the same test identity. Any subsequent correction
to a frozen kernel requires an explicitly versioned protocol and retained old evidence.
Selection and evaluation export reviewable data artifacts and never deploy anything.

Deduplicate evidence into compressed, content-addressed evaluation batches.
Each case retains its independent counts and a hash of the complete timing-free
trace. Development batches also retain public feedback consumed by the optimizer.
No reference answers are sent to the optimizer.

`inspect` regenerates a requested full action/effect trace and verifies it against
its original commitment. `audit` verifies every batch file, reconstructs search and
selection, regenerates distinct policy/case results, and recomputes all comparisons
and intervals. Replay work is additional verification, not extra search budget.
Wall-time measurements and source-environment metadata are not deterministic.
Hashes are content-integrity checks, not signatures or external attestations.

This is a restricted configuration interpreter in trusted Python, not an
operating-system sandbox for untrusted executable agents.
