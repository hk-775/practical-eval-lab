# Preserving business state across agent actions

**Can an agent workflow execute a confirmed subscription change without leaving
billing and access in the wrong state?**

This source-checkout benchmark executes synthetic cancellation and refund
workflows. It compares four control profiles against the same scripted
collaborator pipeline, inspects actual mutations, and verifies final state.
The built-in run needs no API key, network connection, or new dependency.

- **Watch:** open the recorded HTML locally to inspect an animated workflow and
  step through actual proposed actions, tool responses, and committed effects.
- **Understand:** read the [protocol](PROTOCOL.md) and the limitations below.
- **Inspect:** replay the [recorded results](recordings/README.md), including
  condition slices, full JSON evidence, and fingerprints.
- **Adapt:** replace the candidate or add your own policy gate through the
  explicit Python adapter contract below.

All requests, organizations, agents, subscriptions, approvals, and financial
values are invented. Code and synthetic data use MIT-0.

## Reproduce

From the repository root:

```bash
uv sync --locked
uv run --locked python -m benchmarks.subscription_workflow validate
uv run --locked python -m benchmarks.subscription_workflow run \
  --split test \
  --out reports/subscription-comparison.json \
  --html reports/subscription-comparison.html \
  --markdown reports/subscription-comparison.md \
  --require-invariants
uv run --locked python -m benchmarks.subscription_workflow audit \
  reports/subscription-comparison.json
```

Open `reports/subscription-comparison.html` in a browser. It is self-contained,
with no external requests. Moving dashes illustrate direction; they do not
represent measured timing. Motion can be paused, honors reduced-motion
preferences, and becomes static for print or without JavaScript.

The CLI returns 0 on success, 1 for a requested quality-gate failure, 2 for invalid
configuration/evidence, and 3 for candidate execution errors. Unrestricted and
permission-only failures are intentional comparison outcomes, not runner errors.
`--require-invariants` requires complete correct handling and zero unsafe effects
for the reference invariant profile; it does not require a failed external service
to become available.

## What executes

The collaborator performs `billing.cancel`, optionally `billing.refund`, then
`access.set_expiry`. It reads state, receives tool feedback, looks up unknown
outcomes before retrying, and asks or hands off when it cannot proceed.

The guard can bind changes to current confirmed intent: actor, tenant,
subscription, operation, effective date, refund budget, and consent lifetime.
Versions are checked at the mutation boundary. Provider receipts support
idempotency; a new key does not create new refund authority.

The evaluator separately checks all customer-visible effects and final state.
It catches successful API calls that remove prepaid access early, refund twice,
modify the wrong subscription, or continue after consent changes. A repaired final
state does not erase earlier harmful effects.

The four profiles are unrestricted, permissions, business invariants, and deny-all.
Legitimate cancellation completion is measured alongside unsafe effects, so a
system that refuses all work cannot look useful.

## Coverage and limits

There are 120 cases: 40 development, 40 calibration, and 40 frozen test cases,
covering 20 conditions. The partitions have different parameters and wording
but share authored scenario templates. This is a public regression suite, not
an independently sampled or blind enterprise benchmark.

The baseline agents are deterministic scripts. These runs establish properties
of the reference control flow on the supplied cases. They establish no ranking
of LLMs, production incident rate, or deployment certification.

The reference provider is in memory and executes a serial schedule. Companies
must supply their own authenticated consent, durable operation ledger, provider
adapter, concurrency controls, and reconciliation worker. Tax, proration,
provider-specific cancellation semantics, restarts, read confidentiality,
human response time, and real service latency are outside this version.

## How the projects fit

| Project | Integration boundary | Status in this version |
|---|---|---|
| Practical Eval Lab | Execute, grade, compare, and replay | Implemented here |
| Ostiari | Additional authorization/policy decision before mutation | Replaceable `--gate` contract; built-in measurements use the reference guard |
| Escape Lab | Containment and adversarial regression scenarios | Replay, scope, and conflicting-action scenarios implemented here; Escape Lab runtime is not invoked |
| AxonLLM | Select a model-backed next-action candidate | Replaceable `--candidate-factory` contract; no model is invoked in the recordings |

Keep control-system results separate from later model or external-service runs.
An additional policy gate can restrict the reference guard; it cannot override
an invariant denial.

## Adapter contract

A candidate factory is an explicitly trusted local Python callable that creates
a fresh candidate for each episode. The candidate receives only a deep copy of
the public observation: request, actor context, available tools, and the previous
tool result. It returns a JSON-compatible command:

```json
{
  "tool": "billing.cancel",
  "arguments": {
    "subscription_id": "SYN-SUB-1000-A",
    "approval_id": "SYN-CONSENT-1000",
    "operation_id": "SYN-CHANGE-1000",
    "idempotency_key": "SYN-CHANGE-1000:billing.cancel",
    "expected_version": 1,
    "effective_day": 30
  }
}
```

`billing.refund` uses `amount_minor` instead of `effective_day`.
`access.set_expiry` uses `effective_day`. Mutation commands require all five
common identifiers/version fields shown above. `read_state`, `ask_user`, `handoff`,
and `complete` have empty arguments; `lookup_operation` takes `idempotency_key`.
The schema is enforced by [contract.py](contract.py).

The optional gate receives actor context, request, current record, and proposed
command. It must return exactly `{"allow": true}` to allow execution. A denial,
unexpected response, or exception prevents the mutation. It must not treat
candidate-supplied `request.proposals` or `untrusted_note` as consent.

```bash
# Adapt these names to explicitly reviewed local code.
uv run --locked python -m benchmarks.subscription_workflow run \
  --split development --profiles invariants \
  --candidate-factory my_subscription_adapter:create_candidate \
  --gate my_subscription_adapter:authorize \
  --out reports/my-subscription-adapter.json
```

The runner records adapter entrypoints and source-file hashes. Pin the adapter's
complete dependency environment separately, record model/provider revisions and
costs when relevant, calibrate using the calibration partition, and collect fresh
independently grouped scenarios before making generalization claims.
Adapters run with host Python privileges; this observation contract is not a
security sandbox. Configure provider timeouts and resource limits in the adapter.

The built-in auditor replays reference-provider runs. It refuses external-gate
runs without their original gate environment rather than silently substituting
an allow-all response.

## Verification record

Verified locally on October 6, 2026:

- 164 repository tests passed, including 52 subscription checks.
- All 160 recorded test episodes replayed; state, effects, event chains, and
  aggregate/condition metrics matched.
- Chromium verified real connector movement, keyboard pause/resume, reduced
  motion, trace navigation, mobile layout, static printing, and no-JavaScript
  readability. The viewer made no external requests.
- The static site build and browser checks passed; internal links and anchors
  resolved across 133 generated files.
- Gitleaks scanned the new benchmark and generated site. Its generic-key rule
  flagged the ordinary phrase `excessive/duplicate` in the frozen protocol and
  its two generated mirrors. These findings were reviewed as prose false
  positives; no credential was present and no suppression rule was added.
