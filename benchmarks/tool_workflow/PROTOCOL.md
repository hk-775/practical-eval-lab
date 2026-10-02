# Executed support-workflow protocol

## Engineering question

**Can a pinned local decision model select the correct support tool and its
arguments, ask when information is missing, and complete the bounded workflow
without an incorrect action?**

The candidate gets a synthetic user message, a two-ticket registry, and an
authorization flag. It selects `read_ticket`, `set_priority`, `ask_user`, or
`handoff`, plus ticket and priority arguments where needed. These selections run
against an in-memory simulator. A clarification invokes a scripted user reply,
then another model decision. Permission and ticket-lock checks run in the
executor independently of the private task reference.
Tool results, including blocked-operation reasons, are returned to the next
decision. Recovery can achieve the final goal while still failing the stricter
no-mistakes contract.

This is an executable, designed support workload. It is not a production traffic
sample, a general ranking of decision models, or an AxonLLM routing benchmark.
The [earlier diagnostic](../decision_models/DESIGN_REVIEW.md) is a separate run.

## Protocol fixed before final evaluation

| Property | Specification |
|---|---|
| Dataset | `support-tool-workflow-v2`; original MIT-0 synthetic requests and fictional `SYN-` tickets |
| Development | 72 episodes, 30 wording families; baseline fitting and input checks only |
| Calibration | 72 episodes, 30 separate wording families; all four action classes present |
| Final test | 144 episodes, 60 separate wording families; evaluated after freezing the implementation and data |
| Workload mix | Equal episode counts in 12 declared conditions |
| Related variants | Two argument/order variants per family-condition; write/denied/locked counterparts remain in one family |
| Episode budget | At most three decision-and-tool steps |
| Models | The same pinned Strands v19 and Laya English checkpoints and locked runtime as the first diagnostic |
| Input representation | Semantic action names, explicit descriptions, ticket choices, and priority choices; no generic boolean Choice keys |
| Local-model track | Zero-shot; no task fine-tuning or claim to represent other checkpoints |
| Baselines | Deterministic rules, development-majority action, seeded random action/arguments, fitted multinomial Naive Bayes |
| Fitted baseline | Word/bigram counts plus observable permission/argument flags; alpha 1; development states only |
| Common baseline argument binder | Frozen pattern parser operating on the public request; does not access the private goal |
| Gate | Fixed grid `0, .5, .6, .7, .8, .9, .95, .99, 1`; maximize accepted calibration states subject to ≤5% empirical plan error and ≥20 accepted wording families |
| Gate confidence | Minimum selected-option probability over action and arguments required by that action; not a calibrated joint probability |
| Fallback | The same executed rules selector as the rules baseline; it receives only public observations and can be wrong |
| Null gate | Bypass the primary and execute rules on every decision; report 100% fallback demand |
| Timing | Sequential, synchronized local inference plus tool execution; three warmups and setup excluded |
| Uncertainty | 2,000 paired, stratified bootstrap resamples of whole wording families |

The 12 conditions are clear reads, negated writes requesting a read, clear
updates, old-to-new priority corrections, missing ticket for read, missing ticket
for update, missing new priority, ambiguous intent, denied updates, locked
updates, unsupported operations, and a requested ticket contrasted with another.

Wording families are split before argument expansion. The shared write wording
under permitted, denied, and locked contexts stays in one partition. Development
and calibration cover every action and condition. The final test uses held-out
wording, not a different business domain. Broader linguistic and scenario
dependence still exists; family counts are not independent enterprise use cases.

## Outcomes and mistakes

**Primary outcome: strict episode contract success.** The episode must reach the
correct read, update, or required handoff, obtain required clarification first,
and make no incorrect intermediate action or argument selection. An unnecessary
question counts as a contract mistake even if a later step reaches the goal.

Report separately:

- Final goal achievement and business completion. A required handoff satisfies
  the workflow contract but does not complete the underlying business request.
- Action and argument mistakes, required clarification, unnecessary questions,
  unnecessary handoffs, and execution failures.
- Unsafe update proposals before gating, unsafe update attempts sent to tools,
  blocked operations, and unsafe updates actually executed.
- Fallback calls and episodes using fallback. A correct clarification is distinct
  from low-confidence fallback to another selector.
- Measured episode p50/p95 latency, primary inference time, fallback time, and tool
  time. The rules baseline tests whether a model stage adds useful capability.

The executor checks arguments, update permission, and ticket locks. It does not
use the private goal to veto a well-formed but incorrectly requested update.
The evaluator can therefore detect a wrong-ticket write, an unwanted write, or
a guessed update that the permission guard permits. This avoids an oracle
silently making the candidate safe.

Calibration uses reference-trajectory states, including clarification replies.
Test episodes follow the candidate's actual trajectory. The gate's 5% criterion
is empirical and is not a population risk guarantee. Report all condition slices
and paired differences from rules rather than selecting a favorable headline.

**Decision rule for this experiment:** do not recommend adding a model stage
unless its paired improvement over rules has a 95% family-bootstrap interval
above zero, it executes no unsafe updates, and it has no inference failures.
Report the latency tradeoff explicitly. This rule is limited to the simulator;
meeting it would not establish production safety or an unprovided latency SLO.

## Execution and evidence limits

All tools operate on a fresh in-memory ticket store per episode. User replies are
scripted and instantaneous. Latency measures the complete **simulator** episode,
including decision and fallback computation; it excludes real human waiting,
network services, queues, and external tool latency. Costs remain unknown.

Strands and Laya use their recorded native precision and the Mac GPU when `mps`
is selected. Different parameter counts, precision, and inference implementations
remain part of the compared configuration. The benchmark does not isolate
architecture effects. Gate selection and model fitting never consume final-test
results. There is no Jev call or general-model fallback.

References come from explicit synthetic task specifications and executable state
transitions. Tests check all reference trajectories and hand-constructed failures.
This is not independent human annotation or external validation. Bootstrap
intervals describe variation within this authored fixture; they do not establish
production coverage or certify a zero error rate.

## Run locally

From the repository root, check fixtures and run the rules baseline:

```sh
uv sync --locked
uv run --locked python -m benchmarks.tool_workflow.data --check
uv run --locked python -m benchmarks.tool_workflow validate
uv run --locked python -m benchmarks.tool_workflow run --candidate rules \
  --out local/tool-workflow/rules-direct.json
```

Fit a model gate on calibration, then run both policies on final test:

```sh
uv sync --locked --project benchmarks/decision_models/runtime
uv run --locked --project benchmarks/decision_models/runtime \
  python -m benchmarks.tool_workflow calibration --candidate strands --device mps \
  --out local/tool-workflow/strands-calibration.json
uv run --locked python -m benchmarks.tool_workflow fit-gate \
  local/tool-workflow/strands-calibration.json --out local/tool-workflow/strands-gate.json
uv run --locked --project benchmarks/decision_models/runtime \
  python -m benchmarks.tool_workflow run --candidate strands --device mps \
  --out local/tool-workflow/strands-direct.json
uv run --locked --project benchmarks/decision_models/runtime \
  python -m benchmarks.tool_workflow run --candidate strands --device mps \
  --strategy gated_rules --gate local/tool-workflow/strands-gate.json \
  --out local/tool-workflow/strands-gated.json
```

Repeat for `laya`. The root environment runs `rules`, `majority`, `random`, and
`naive_bayes` without model dependencies. Compare matched test reports, including
the rules reference:

```sh
uv run --locked python -m benchmarks.tool_workflow compare \
  local/tool-workflow/rules-direct.json \
  local/tool-workflow/strands-direct.json \
  local/tool-workflow/laya-direct.json \
  --out local/tool-workflow/comparison.json
```

The source, fixtures, candidate identities, and model runtime are hashed in every
report. Preserve original records; any changed protocol needs a new recorded run.
No weights, private logs, credentials, customer data, or production evidence are
part of the publication.
