# Executed support-workflow evaluation

**Can a local decision model select the correct tool and arguments, ask when
information is missing, and complete a support workflow without a mistaken
action?**

This evaluation runs Strands Decider v19, Laya English, and lightweight baselines
against an executable synthetic ticket-support simulator. It measures tool
execution and state changes, clarification, authorization failures, fallback,
and complete simulator-episode latency.

Read the [frozen protocol](PROTOCOL.md) for the engineering question, workload,
grouped partitions, calibration procedure, metrics, baselines, reproduction
commands, and limitations. The protocol and implementation are hashed before
calibration and final-test runs.

The workload has 72 development episodes, 72 calibration episodes, and 144 final
test episodes. Related wording, argument variants, and permission counterparts
stay in one split. Every split includes all action classes and all 12 conditions.

All requests and records are synthetic. The results concern this bounded support
simulation. Real service latency, human response time, production traffic, and
Jev performance are outside its evidence.

The [earlier decision-model diagnostic](../decision_models/DESIGN_REVIEW.md)
remains a separate historical experiment with its design limitations documented.
