# Tool calling: an average improvement can hide a regression

**Task.** Select one simulated `lookup_order`, `create_ticket`, or `no_action`
call. Grade the tool, arguments, and the side-effect-free simulator outcome.
This suite is one tool decision; the [agent example](agent.md) covers a workflow.

```bash
uv run --locked eval-lab compare --suite tool_calling --split holdout
uv run --locked eval-lab compare --suite tool_calling --split holdout \
  --fail-on-regression --critical-tag vocabulary --min-slice lookup=1
```

Development is 12/20 → 20/20. Holdout is 5/10 → 8/10, with four improvements and
one regression. The second command intentionally exits 1. The baseline acts on
any order number, including cancellation requests and sample IDs. The change
requires a recognized lookup intent, but misses “Could you locate A-104?”

**Why these measurements?** Tool selection alone misses wrong order IDs or ticket
arguments. Simulated outcome checks make effects inspectable. A regression gate
protects previously passing behavior, a critical tag requires every tagged
execution to pass, and a slice minimum protects a subset. Gate tags must exist;
a typo cannot silently disable a check.

**Limits.** The simulator has three tools and no external effects. It cannot
validate a real service's authorization, delivery, or idempotency behavior. Those
need integration tests against an appropriate isolated service.

**Try it.** Add “locate” support to a candidate and check whether it accidentally
acts on a negated lookup. Keep the regression visible until the application change
passes both positive and negative cases; changing the label is a different test.

[Recorded experiments](results/README.md) · [Dataset](../eval_lab/data/tool_calling)
