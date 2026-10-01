# Classification: a score can hide the wrong failures

**Task.** Route a support ticket to Hardware, Software, or Other. Procurement is
Other even when the request names a device. Success is the correct label, with
optional case/whitespace normalization. Extra explanations do not count as labels.

```bash
uv run --locked eval-lab compare --suite classification --html reports/classification.html
uv run --locked eval-lab compare --suite classification --split holdout
```

The development comparison is 14/20 → 20/20. The change gives procurement/general
requests precedence over hardware keywords and adds a few device words in another
language. Holdout improves from 4/10 to 7/10; unfamiliar vocabulary still fails.
The holdout command exits 1 at the default 80% gate.

**Why these measurements?** Accuracy answers how often the routing decision is
right. The confusion matrix identifies which classes get mixed up. Macro-F1 gives
each of the three labels equal weight; the implementation uses normalized labels
for this diagnostic even when the exact-label pass check is enabled. Missing
classes receive F1=0, so interpret small custom datasets carefully. Tag slices
show specific language and business-rule failures with their denominators.

**Limits.** Keyword rules do not understand arbitrary tickets. These small,
authored examples cannot establish deployment accuracy or demographic fairness.
A language slice is not a substitute for a representative multilingual dataset.

**Try it.** Export the development profile, add a ticket where hardware is
mentioned but the problem is a software driver, and decide the reference before
running. Compare the per-class errors, not just the overall percentage. Then run
your own application using [named candidates](../docs/integrations.md).

[Recorded experiments](results/README.md) · [Dataset](../eval_lab/data/classification)
