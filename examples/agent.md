# Multi-step agents: verify what the tools actually did

**Task.** Resolve a simulated return request. An eligible return requires an
existing, delivered, returnable order no older than 30 days. Look up the order,
check eligibility, then create the return. Unsupported requests must invoke no
tools. Retry transient failures within the call budget. Report missing orders or
exhausted budgets as unavailable.

```bash
uv run --locked eval-lab compare --suite agent --html reports/agent.html
uv run --locked eval-lab compare --suite agent --split holdout --critical-tag critical
```

Development improves 4/8 → 8/8; holdout improves 1/4 → 4/4. The baseline follows the three-step workflow but stops at its first transient
failure and mishandles unsupported requests. The changed candidate checks intent
first and retries within the budget. The recorded comparisons show which failures
change; every tool remains an in-memory simulation with no actual orders or money.

**Why these measurements?** A trace records `{tool, arguments, result}` for each
call. The grader independently replays calls through the simulator. It rejects
unknown tools, wrong order IDs, skipped eligibility checks, duplicate returns,
fabricated results, and excessive calls. Goal completion depends on replayed
state, not the candidate's final claim. “Unavailable” requires evidence: an actual
missing-order result or an exhausted retry budget. An empty trace cannot prove it.

**Limits.** The candidate and grader share the simulator's tool semantics; a bug
in that simulator is a shared assumption. Negative tests and explicit reference
goals help, but a real integration needs independent service contracts and tests.
The fixture's failure schedule is visible in input for reproducibility. It is not
a hidden environment or a measurement of planning capability. General agents need
richer traces, permissions, idempotency, and real environment outcome checks.

**Try it.** Add a second transient failure and reduce the budget. Check both goal
completion and termination. Register a Python candidate that runs a real agent
against isolated test tools and adapts its trace to this contract. Do not connect
write-capable production tools merely to run a teaching eval.

[Recorded experiments](results/README.md) · [Dataset](../eval_lab/data/agent)
