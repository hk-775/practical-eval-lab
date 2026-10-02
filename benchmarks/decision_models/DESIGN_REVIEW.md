# Decision model evaluation: design review

**Status: exploratory diagnostic only.** The 2 October 2026 fixture establishes
that the pinned adapters execute and exposes behavior on specific inputs. It does
not establish which model should be selected for an enterprise workload.

The [recorded outputs](recordings/README.md) remain intact. The arithmetic is
reproducible; the limitations below concern what the experiment measures.

## Problems in the first design

| Issue | Evidence in this fixture | Consequence |
|---|---|---|
| Too few distinct scenarios | Four holdout scenario groups per family; four variants per group | 64 decisions are not 64 independent tasks. Repeating them three times adds timing observations, not task diversity. |
| Model-facing options introduce a confound | Half the decisions are policy probes with generic `yes`/`no` Choice keys and descriptions | The score mixes task ability with a documented label-sensitivity issue. |
| Checkpoint purpose differs | The selected Laya checkpoint is the English base; upstream describes specialization as necessary for typed decisions | The result cannot characterize specialized Laya deployments or establish the best available configuration. |
| Calibration misses important classes | Routing calibration has only `small` and `code`; tool calibration has only `lookup` and `update`. Neither contains `clarify`. | The fitted gate is not calibrated across the intended decision space. |
| The objective is underspecified | Manually assigned `small`/`reasoning`/`code` labels; no downstream model executes | This measures agreement with task-category labels, not whether routing improves model quality, latency, or cost. |
| Aggregate weighting is arbitrary | Policy contributes 32 decisions; routing and tools contribute 16 each | One headline accuracy hides different tasks and reflects the chosen question count. |
| Baseline is weak | An untrained lexical softmax, with no majority, fitted classifier, or executed fallback | The experiment lacks useful deployment comparators. |
| Deployment behavior is absent | Short sequential inputs, one machine, no executed tools or fallback | Request timings do not establish system latency, throughput, enforcement, or economic benefit. |

### Source of the Laya concern

The pinned [Laya README, “Honest limits”](https://github.com/NandhaKishorM/laya/blob/fa9a2a7070b1789912a49ae24603bbfb1a78b001/README.md#honest-limits)
warns that boolean-word Choice keys can dominate their descriptions, recommends
semantic or neutral keys, and describes weak zero-shot typed-decision performance
of the base checkpoints. It also warns that semantic labels alone do not resolve
negation failures.

This does not make an adversarial label probe invalid. It makes its interpretation
specific: the result describes that input representation. Such probes should be
reported separately from a representative task-quality score. A different
checkpoint or representation must be measured; neither can be assumed to fix it.

### What the gate does and does not show

The 5% figure was an empirical calibration-selection rule, not an estimated
production error bound. Strands accepted 11 unique holdout decisions with no
observed errors; related variants make those observations dependent. Laya's null
gate means this calibration procedure selected no usable operating point.
It does not show that no useful operating point exists after appropriate task
design or specialization.

### Findings that remain useful

- Both pinned models executed the specified Choice contract, with no scored
  execution errors in this run.
- The raw outputs demonstrate particular failures, including Strands returning
  identical answers to opposite policy questions under the tested representation.
- The latency measurements describe the recorded Mac configuration and request
  sequence.
- Report provenance, probability validation, grouping, gate isolation, and static
  publication can be reused in a better experiment.

## Replacement design

### 1. State a deployment question

Start with one bounded capability: **select the next tool in a synthetic support
workflow, or abstain when required information is missing**. Measure the action
and arguments against a deterministic simulator's state transition and final
outcome. Keep authorization enforcement in the simulator, with explicit rules.
Do not claim that a classifier's policy answer enforces authorization.

For an eventual AxonLLM routing benchmark, the question is different: **does a
router reduce measured cost or latency while preserving downstream task quality?**
That requires actually running candidate models and the fallback on matched
tasks. Handwritten capability labels cannot supply the answer. API access is not
inherently required, but any local downstream models need their own measured
configurations and adequate compute.

### 2. Establish valid input representations on development cases

Use disjoint development examples to check each checkpoint's documented input
format, token budgets, and positive and negative controls. For Choice, start with
semantic actions and explicit descriptions. Map predictions back to common
actions before scoring.

Freeze two separately reported configurations if useful:

- **Common representation:** identical model-facing input for every candidate.
- **Documented configuration:** candidate-specific formatting selected only on
  development data, with the exact mapping and settings recorded.

Keep boolean-label, question-inversion, instruction-injection, option-order, and
irrelevant-context probes as a separate robustness set. Do not silently tune a
checkpoint or prompt against the already inspected v1 holdout.

### 3. Build independent, reviewable task families

Create a substantially larger set of distinct situations across ambiguity,
missing arguments, negation, read/write intent, and policy boundaries. Specify
the intended workload mix. Include all decision classes in development and
calibration. Split scenario families before producing paraphrases or variants.

References should follow explicit rules or executable outcomes and receive
independent review where judgment is required. Keep calibration and final test
labels outside the tuning loop. Set the number of independent scenarios from the
desired uncertainty and error bounds, rather than inflating counts with repeated
trials.

### 4. Compare useful alternatives

Include deterministic rules where applicable, majority and random references,
a fitted lightweight classifier, both selected model configurations, and an
executed general-model fallback if available. Keep zero-shot and task-specialized
tracks separate. Disclose any overlap between checkpoint training data and public
test data; do not substitute a benchmark-trained checkpoint into an allegedly
independent test.

### 5. Measure the system and uncertainty

Predeclare the principal outcome and acceptance criterion. Report task success,
per-class errors, unsafe attempted and executed actions separately, risk versus
coverage, and confidence intervals that respect scenario groups. Select gates on
representative calibration data and check them once on the final test.

For latency, separate initialization, first-use requests, and warmed requests;
vary relevant input lengths, numbers of questions/options, and concurrency.
Count retries, abstentions, and actual fallback execution. Report cost only when
the required resource or API measurements exist.

## Publication decision

Keep the first run labeled as a diagnostic with this design review attached.
Do not promote its 75.0% versus 37.5% scores as a general model ranking, Jev
replacement assessment, production readiness result, or enterprise benchmark.
The repository PR is held as a draft while the evaluation objective and
replacement design are reviewed.
