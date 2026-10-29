# Can the improvement process improve?

A bounded recursive self-improvement experiment for subscription workflow recovery.
Compare a fixed agent, a fixed optimizer, and an optimizer whose own configuration
can evolve. Inspect every proposal, accepted revision, selected artifact, and
executed final outcome.

**This version runs local finite configuration search.** It does not invoke an
LLM, train model weights, rewrite arbitrary code, or update a deployed agent.
All workloads and records are synthetic. Original code and cases use MIT-0.

## Run it

From the source checkout, using the committed dependency lock:

```bash
uv sync --locked
uv run --locked python -m benchmarks.recursive_improvement validate

# Development search followed by validation selection. No final-test feedback.
uv run --locked python -m benchmarks.recursive_improvement search \
  --out reports/rsi-search.json

# Verify the committed selection, then run the separate final evaluation.
uv run --locked python -m benchmarks.recursive_improvement evaluate \
  --search reports/rsi-search.json --out-dir reports/rsi-final

# Independently reconstruct search, selection, selected-policy actions and results.
uv run --locked python -m benchmarks.recursive_improvement audit \
  reports/rsi-final/comparison.json
```

Open `reports/rsi-final/comparison.html` locally. The report includes final results,
paired seed differences, development curves, and an interactive generation viewer.
Animated connectors illustrate the search loop; they are not measured timing.
Pause/resume works with the keyboard, reduced-motion is respected, and the static
tables and chart work without JavaScript or when printed. There are no external
requests.

Every command refuses to overwrite an existing evidence artifact. Use fresh output
paths for reproduction. CLI exit 0 means a valid run completed, including a null or
negative experimental result. Exit 2 means configuration, integrity or execution
validation failed. A successful command is not deployment approval.

The [recorded run](recordings/README.md) includes all three arms and all five seeds.
Read the [protocol](PROTOCOL.md) before interpreting the results.

## What is recursive here?

Each artifact contains two small programs expressed as finite configurations:

| Component | Mutable behavior |
|---|---|
| Workflow policy | Unknown-outcome recovery, missing-receipt recovery, access retry count, proposal repair, missing-date clarification |
| Improvement strategy | Last/all failure attribution, frequency/rarity/random field ordering, one/two-field edits |

The recursive arm can propose a changed improvement strategy, use it to generate
a workflow revision, and retain both when the observed development result improves.
That retained strategy generates proposals in subsequent generations. The complete
before/after change and the strategy actually used are recorded.

The outer search algorithm and selection rule remain fixed. There are 96 possible
workflow configurations and 12 optimizer configurations. This intentionally small
search space makes the mechanism auditable and reproducible. Results do not
establish open-ended self-improvement or gains for a language model.

## What the experiment protects

Configuration artifacts accept only typed, enumerated JSON fields. They cannot
express file paths, commands, imports, network access, or edits to the verifier.
Unknown fields, duplicate JSON keys, oversized artifacts, and invalid types fail
validation. There is no arbitrary-code plug-in API.

The unchanged [subscription executor](../subscription_workflow/README.md) applies
current consent, tenant/resource scope, refund budgets, and provider idempotency.
Its separate grader checks actual effects and final state. The previous frozen
subscription experiment and evidence remain intact.

This is a restricted configuration language inside trusted Python, not an OS
sandbox for untrusted executable code. The operator still controls the repository.
Hashes detect content changes; they are not signed provenance.

## Fair comparison and limitations

- All arms start from the same agent and optimizer.
- The default plan uses five paired seeds and eight generations, with two candidate
  trials per generation. Each arm receives 17 development evaluations and nine
  validation evaluations per seed. Every repeated candidate consumes its allowance.
- Actual simulated provider-call counts are reported. Evaluation allowance is not
  identical CPU time, model tokens, cost, or external latency.
- The fixed optimizer uses all failure signals, frequency ordering, and a one-field
  edit width. The recursive arm may explore two-field edits. Results are relative
  to these specified strategies; a tuned fixed optimizer could perform differently.
- Development, validation and test contain 24, 18 and 24 episodes. Families have
  distinct authored fault compositions, including different combinations and deeper
  outages. They share an author, simulator and fault vocabulary. They are not
  independently sampled enterprise traffic or independently authored test suites.
- Search gets development signals only. Validation selects a checkpoint after
  search ends. The selected set is hashed before the separate final evaluation.
- The final test is public and author-visible. After examining it, do not tune
  against it and continue describing it as untouched.
- All arms use the same invariant guard. Zero observed unsafe effects do not mean
  the optimizer learned authorization or that production safety is established.
- Repeated seeds reuse cases. Report the paired differences; do not infer a
  production incident rate or treat all episodes as independent trials.
- Correct handoff during permanent provider failure is distinct from completed
  business work. Denying all work cannot satisfy legitimate completion.
- Finite-search null and negative results are retained. No candidate is deployed.

## Reviewable outputs

`evaluate` writes:

- `comparison.json`: complete search/selection record, final action traces,
  committed effects, metrics, per-seed comparison and review eligibility.
- `comparison.html`: self-contained interactive evidence viewer.
- `comparison.md`: static summary and content identities.
- `candidates/<seed>-<arm>.json`: exact selected workflow and optimizer configuration.
- `candidates/<seed>-<arm>.changes.json`: the change from the starting artifact.

Selected candidates are frozen before final testing. Eligible candidates are
marked for human review; passing the test does not execute a deployment action.

`audit` reconstructs the search under the recorded seeds, checks selection,
regenerates actions from selected configurations, replays the tool calls, and
recomputes effects, metrics and review flags. Tests cover tampering even when an
altered report is given a newly computed content hash.

To update the presentation without rerunning evidence:

```bash
uv run --locked python -m benchmarks.recursive_improvement render \
  reports/rsi-final/comparison.json \
  --html reports/rsi-presentation.html --markdown reports/rsi-presentation.md
```

## Relationship to the project cohort

| Project | Proposed future use | Status here |
|---|---|---|
| Practical Eval Lab | Search, measurement, versioned evidence and review | Implemented locally |
| Enterprise workflow agents | Consume qualified workflow revisions | No runtime connection |
| AxonLLM | Study routing policies using a separately defined task and reward | No runtime connection |
| Ostiari | Enforce authorization outside an optimizer's editable scope | Reference subscription guard only; no Ostiari service called |
| Escape Lab | Validate containment and adversarial cases independently | No Escape Lab runtime called |

For a model-driven follow-up, define a JSON-only proposal interface, isolated
execution for any code-writing extension, model/token budgets, independent scenario
authors, and a new frozen protocol. Keep those results separate from this local
configuration-search experiment.

## Research context

This experiment takes inspiration from the distinction between improving an agent
and improving the process that produces subsequent agent revisions:

- [Darwin Gödel Machine](https://arxiv.org/abs/2505.22954): evaluation-guided changes
  to coding agents and their tooling.
- [Hyperagents](https://arxiv.org/abs/2603.19461): improving task behavior together
  with the improvement mechanism.

This implementation is an original, smaller configuration-search experiment; it
does not reproduce either paper's implementation or reported results.

## Verification record

Verified locally on 29 October 2026 UTC:

- 207 repository tests passed, including 43 checks for the new experiment.
- Deterministic search and selection reproduced across separate Python processes
  with different hash seeds.
- All 360 final episodes replayed; selected-policy actions, effects, metrics and
  review flags matched the recorded evidence.
- The static build produced 74 HTML pages and 175 total files; internal links and
  anchors resolved.
- Chromium checked generation navigation, actual connector motion, keyboard
  pause/resume, reduced motion, mobile overflow, printing, no-JavaScript fallback,
  and absence of external requests. Desktop and mobile screenshots were inspected.
- Gitleaks scanned the experiment and reported one generic-key finding in the
  frozen JSON: a generated `SYN-OP-…:billing.cancel` idempotency value. It is a
  deterministic synthetic operation identifier, not a credential. The finding
  was reviewed; no suppression or evidence rewrite was introduced.
