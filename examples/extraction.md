# Structured extraction: valid JSON can still be wrong

**Task.** Extract `order_id`, positive integer `quantity`, singular `item`, and
`priority` from an order request. Missing values are null; unspecified priority is
normal. This lesson defines “not urgent” and “no rush” as low priority.

```bash
uv run --locked eval-lab compare --suite extraction --html reports/extraction.html
uv run --locked eval-lab compare --suite extraction --split holdout
```

Development improves 10/20 → 20/20; holdout improves 3/10 → 8/10. The change adds
case-insensitive matching, selected number words, and negation handling. It still
misses vocabulary such as `six` and `printers` in the holdout data.

**Why these measurements?** JSON-object validity and schema checks distinguish
formatting failure from incorrect values. Per-field pass rates identify whether
quantity, item, priority, or order ID is responsible. `true` is rejected as a
quantity even though Python booleans are integer subclasses. An incorrect value
still fails when extra fields are allowed.

**Limits.** Exact field equality assumes one agreed normalization. It does not
measure whether a different wording means the same thing. The schema is intentionally
small, and execution errors are reported separately from per-field measurements.

**Try it.** Add a missing-quantity case and an ambiguous priority case. Agree the
null/ambiguity convention first. Compare two prompts through the optional model
adapter, preserving the same profile, and use multiple trials to inspect variability.

[Recorded experiments](results/README.md) · [Dataset](../eval_lab/data/extraction)
