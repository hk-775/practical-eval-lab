# Contributing

Start with one small failure you can explain. Use synthetic cases and keep
datasets readable. See [the learning guide](docs/learning-guide.md).

```bash
uv sync --locked
uv run --locked pytest -q
uv run --locked playwright install chromium
uv run --locked python -m scripts.browser_check
```

Cases live in `eval_lab/data/<suite>/dev.jsonl`. Each case needs a unique `id`,
an `input`, an `expected` answer matching the suite contract, and a list of tags.
Explain the expected answer in the PR if it is debatable. Keep a separate holdout
set and disclose when a candidate was designed using those cases.

Graders live in `eval_lab/suites.py`; candidates live in `eval_lab/candidates.py`.
Add behavior tests for new graders, invalid data, or persistence changes.
Do not assert that model output is perfectly repeatable. Do not add paid model
calls or secrets to CI.

Run both candidates on the same dataset and grader. Report regressions as well
as improvements. A change to labels or grading rules creates a new test; it is
not evidence that the old candidate got better.

Local profiles, reports, caches, screenshots, and environment files are ignored.
Review an exported profile before sharing it: it includes all of your inputs
and expected answers.

Contributions are distributed under the project’s [MIT-0 license](LICENSE).
Submit only code and data that you have authority to contribute under those terms.
