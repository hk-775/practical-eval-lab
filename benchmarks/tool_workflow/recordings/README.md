# Executed support workflow: recorded results

**Recorded 2 October 2026.** On this bounded synthetic workflow, the tested
zero-shot model configurations did not justify adding a model stage ahead of
the rules selector. Rules completed 124 of 144 episodes without mistakes.
Neither local model satisfied the frozen improvement-and-error criterion.

These are simulator outcomes, not production evidence or a general model
ranking. The [protocol](../PROTOCOL.md), [freeze record](../freeze.json), and
[input-budget audit](../input-audit.json) are available for inspection. The code
and protocol were committed at `2aa9e2a` before calibration and final-test runs.

## What was tested

A selector chooses a support tool and arguments from a user request, two ticket
records, authorization, and the last tool result. The simulator actually reads
records, updates priority, supplies scripted clarification replies, or records
a handoff. Permission and lock guards operate independently of task references.

The test has **144 episodes in 60 held-out wording families**, balanced across
12 conditions. Development and calibration each have 72 episodes in 30 other
wording families. Related slot/order and permission variants stay in one split.
The test is one recorded pass per configuration, not repeated copies presented
as more independent tasks.

**Strict success** requires the correct terminal outcome, required clarification,
and no incorrect intermediate action or argument. Final goal achievement and
business completion are recorded separately; appropriate handoff does not
complete the underlying business request.

## Direct selector results

| Selector | Strict successes | Success rate | 95% family interval | Correct initial clarification | Incorrect writes accepted |
|---|---:|---:|---:|---:|---:|
| Rules | 124 / 144 | 86.1% | 80.6–90.3% | 48 / 48 | 0 |
| Fitted Naive Bayes | 60 / 144 | 41.7% | 33.3–50.7% | 29 / 48 | 7 |
| Strands Decider v19 | 39 / 144 | 27.1% | 21.5–32.6% | 0 / 48 | 50 |
| Laya English | 35 / 144 | 24.3% | 19.4–29.2% | 0 / 48 | 23 |
| Development-majority action | 26 / 144 | 18.1% | 16.7–20.8% | 0 / 48 | 0 |
| Seeded random policy | 14 / 144 | 9.7% | 6.2–13.2% | 10 / 48 | 22 |

The intervals resample whole wording families within template banks, retaining
related slot and permission variants. They describe variability within this
authored fixture, not confidence in production reliability.

“Incorrect writes accepted” counts executed `set_priority` calls that violated
the private task contract, including unwanted writes, wrong arguments, and
guessed updates before clarification. A write counts as executed even if it sets
the existing value. **25 of Strands' 50 incorrect writes changed a value; 5 of
Laya's 23 did; all 7 of Naive Bayes' incorrect writes did.** This distinguishes
an incorrect tool invocation from its material state change.

Strands eventually reached the reference terminal goal in 59 episodes, but only
39 were mistake-free. The stricter primary score does not credit recovery as
an error-free trajectory. Rules' 124 successes comprised 88 completed reads or
updates and 36 appropriate handoffs.

### Simulator-episode latency

| Selector | Median | p95 | Selector calls |
|---|---:|---:|---:|
| Rules | 0.061 ms | 0.153 ms | 232 |
| Fitted Naive Bayes | 0.111 ms | 0.188 ms | 293 |
| Strands Decider v19 | 453.8 ms | 1,339.6 ms | 206 |
| Laya English | 125.0 ms | 412.5 ms | 235 |

These timings include the actual decision trajectory, tool execution, and any
scripted clarification turns. They pool successful and failed episodes;
candidates can fail after different numbers of steps. They are not a comparison
at equal task quality or a pure inference-speed measurement.

All tools run in memory and scripted user replies have no human waiting time.
Setup and three warmups are excluded. Real service latency, queues, human
response time, and monetary cost remain unmeasured. All scored model calls
completed without inference or response-validation errors.

## Calibration and executed fallback

The predeclared gate required at most 5% empirical calibration plan error and
coverage of at least 20 wording families. **No candidate met both requirements
at any threshold on the fixed grid.**

| Candidate | Illustrative calibration point | Why it did not qualify |
|---|---|---|
| Naive Bayes | Threshold 0.95: 2 errors / 46 accepted states, 19 families | Error criterion met; minimum family coverage missed |
| Strands | Threshold 0.60: 5 errors / 29 states, 20 families | Error rate too high; at 0.70 only 3 states/families remain |
| Laya | Threshold 0.50: 40 errors / 53 states, 23 families | Error rate too high; higher thresholds do not meet the combined criterion |

The complete grids, including zero-coverage points, are in the gate JSON files.
The criterion was not relaxed after seeing results.

Each null gate bypassed its primary selector and actually invoked the rules
fallback. All three gated configurations therefore produced:

- **124 / 144 strict successes**, identical to the rules baseline.
- **100% fallback demand**, with **zero primary model/classifier calls**.
- **Zero incorrect writes accepted**.
- A paired success difference from rules of **zero**.

Their measured p95 episode latencies were 0.141 ms for the Naive Bayes policy,
0.200 ms for the Strands policy, and 0.201 ms for the Laya policy. These are
rules-only paths; they are not accelerated model inference or model success.
Small timing differences between those paths are not evidence of a quality or
architectural advantage.

## Where the failures occurred

Every condition below has 12 test episodes.

| Condition | Rules successes | Naive Bayes | Strands | Laya |
|---|---:|---:|---:|---:|
| Clear read | 10 | 2 | 7 | 8 |
| Read with a negated write | 10 | 4 | 3 | 7 |
| Clear update | 12 | 10 | 11 | 5 |
| Old-to-new priority correction | 8 | 7 | 10 | 7 |
| Missing ticket for read | 12 | 8 | 0 | 0 |
| Missing ticket for update | 12 | 12 | 0 | 0 |
| Missing new priority | 12 | 4 | 0 | 0 |
| Ambiguous requested operation | 12 | 5 | 0 | 0 |
| Update permission denied | 12 | 2 | 1 | 0 |
| Requested ticket locked | 12 | 2 | 0 | 0 |
| Unsupported operation | 12 | 2 | 0 | 0 |
| Ticket contrasted with another | 0 | 2 | 7 | 8 |

Rules were not perfect: they failed all 12 contrastive-reference episodes and
eight other episodes, generally asking unnecessary questions. Both local models
resolved some references and corrections that the rules missed, but failed to
ask for required information and performed worse across the full declared mix.
The experiment does not establish that those capabilities could never be useful
in another, separately evaluated architecture.

The guard blocked 79 Strands operations and 136 Laya operations. It could not
prevent an authorized, well-formed operation that contradicted the user's
request. That is why the report distinguishes model proposals, tool attempts,
blocked operations, accepted writes, and actual state changes.

## Configuration and interpretation

- Hardware: Apple M4 Pro, 48 GiB unified memory, macOS arm64, Python 3.13.12.
- Strands and Laya: the pinned checkpoints and source revisions from
  [models.json](../../decision_models/models.json), cached locally and executed
  sequentially on `mps`. No model API keys, Jev calls, or paid services.
- Native precision: Strands backbone bfloat16; Laya float32. Compilation is
  disabled. These are configuration comparisons, not architecture ablations.
- Laya is the English base checkpoint, not a specialized typed-decision model.
  Neither model was fine-tuned on this workflow.
- The rules and argument binder were authored against the workflow specification.
  Naive Bayes was fitted only on development reference states. They never receive
  the private test goal. The fallback can fail and is not an oracle.
- The pinned Laya renderer was checked over 384 reference states and 1,152
  questions. Maximum head length was 143 tokens; maximum sequence length was
  252. No instructions, options, or state text were truncated.
- Natural omissions, not text announcing which field is missing, appear in the
  frozen missing-information cases. Opaque randomized ticket identifiers do not
  encode the condition.

**Engineering conclusion:** keep the rules selector as the reference for this
bounded workflow. These tested zero-shot model stages did not earn deployment
under the frozen criterion. The rules' remaining failures still require work;
86.1% is not a claim of production readiness. Further specialization or a
different selector architecture would require a new protocol and fresh final
test families.

## Raw evidence and replay

| Selector | Direct execution | Calibration | Gate | Gated execution |
|---|---|---|---|---|
| Rules | [JSON](2026-10-02/rules-direct.json) | — | — | — |
| Majority | [JSON](2026-10-02/majority-direct.json) | — | — | — |
| Random | [JSON](2026-10-02/random-direct.json) | — | — | — |
| Naive Bayes | [JSON](2026-10-02/naive_bayes-direct.json) | [JSON](2026-10-02/naive_bayes-calibration.json) | [JSON](2026-10-02/naive_bayes-gate.json) | [JSON](2026-10-02/naive_bayes-gated_rules.json) |
| Strands | [JSON](2026-10-02/strands-direct.json) | [JSON](2026-10-02/strands-calibration.json) | [JSON](2026-10-02/strands-gate.json) | [JSON](2026-10-02/strands-gated_rules.json) |
| Laya | [JSON](2026-10-02/laya-direct.json) | [JSON](2026-10-02/laya-calibration.json) | [JSON](2026-10-02/laya-gate.json) | [JSON](2026-10-02/laya-gated_rules.json) |

[Matched comparison JSON](2026-10-02/comparison.json) contains paired differences,
family intervals, report hashes, and the fixed decision criterion. All nine
execution reports were replayed against fresh simulator state and their metrics
recomputed without invoking a model.

```sh
uv run --locked python -m scripts.audit_workflow_recordings \
  benchmarks/tool_workflow/recordings/2026-10-02/strands-direct.json
```

The archive verifier canonicalizes source path labels to replay these Mac
recordings on other operating systems while preserving the frozen implementation.

Content hashes detect accidental changes; they are not signed execution
attestations. Original code, fixtures, and recordings use MIT-0. Upstream model
and runtime licenses remain separate; weights are not bundled.
