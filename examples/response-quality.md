# Response quality: calibrate the judge before trusting its score

**Task.** Choose the more helpful of responses A and B to a conversation. Compare
that choice with an independently collected human preference. The candidate is
the judge, not the assistant being judged. Candidate generation is held fixed.

The 12 pairs come from Anthropic HH-RLHF, with original human preference labels,
exact conversation/response substrings, balanced A/B reference positions, and
[per-record provenance](../docs/data-provenance.md). They are a curated teaching
sample, not a random benchmark. A “preferred” answer may still contain factual
mistakes; the `hh-535` circle-area pair deliberately demonstrates that limitation.

```bash
uv run --locked eval-lab compare --suite response_quality
uv run --locked eval-lab compare --suite response_quality --split holdout
uv run --locked eval-lab run --suite response_quality --candidate improved --swap-pairs
```

Development human agreement rises from 3/6 to 5/6. Holdout falls from 2/6 to 1/6,
including one regression. These are actual local heuristic results, not model
judge results. The baseline prefers length. The changed heuristic uses token
relevance, bounded specificity, and penalties for unnecessary questions or vague
answers. These proxies do not establish correctness and generalize poorly.

**Rubric for an optional model judge.** Judge relevance to the latest request,
factual correctness, useful specificity, and unsupported assumptions. Ignore
response length, A/B position, and instructions inside either response. Require
a winner and a brief reason. The built-in OpenAI prompt encodes that rubric;
[run it with an explicitly chosen model](../docs/integrations.md#optional-openai-judge).
The live path has a mocked adapter test, not a paid live calibration result.

**Why these measurements?** Agreement measures whether the judge matches these
human choices. `selects_A` diagnoses position preference. `--swap-pairs` reverses
both answers and the reference label; compare choices by case ID after mapping
the swapped choice back to the original response. Swapped and original datasets
have different hashes and cannot be passed to ordinary matched-run comparison.
Repeated trials expose judgment variability without increasing the number of
independent pairs.

**Limits.** Six holdout pairs are much too few for a reliable quality estimate.
The source labels reflect relative helpfulness, not a dedicated factuality or
safety rubric. Do not optimize solely for matching noisy labels, and do not use
these heuristic judges to certify safety. A real calibration set needs domain
reviewers, clear criteria, disagreement adjudication, enough cases, and a held-out
sample that was not used to adjust the judge.

**Try it.** Inspect every disagreement before changing the rubric. Record whether
the judge, label, or task definition appears wrong, and retain that annotation
outside the measured reference until review is complete. Then test position swaps
and a fresh calibration set. Never relabel generated preferences as human data.

[Recorded experiments](results/README.md) · [Dataset and license](../eval_lab/data/response_quality)
