# Contributing

Start with one small failure you can explain. Use synthetic cases and keep
datasets readable. See [the learning guide](docs/learning-guide.md).

```bash
uv sync --locked
uv run --locked pytest -q
uv run --locked playwright install chromium
uv run --locked python -m scripts.browser_check
uv run --locked python -m scripts.package_check
uv run --locked python -m scripts.reproduce_portfolio
```

Cases live in `eval_lab/data/<suite>/dev.jsonl`. Each case needs a unique `id`,
an `input`, an `expected` answer matching the suite contract, and a list of tags.
Explain the expected answer in the PR if it is debatable. Keep a separate holdout
set and disclose when a candidate was designed using those cases.

Graders and task logic live in `eval_lab/suites.py` and `eval_lab/advanced.py`;
candidate adapters live in `eval_lab/candidates.py` and `eval_lab/integrations.py`.
Add behavior tests for new graders, invalid data, or persistence changes.
Do not assert that model output is perfectly repeatable. Do not add paid model
calls or secrets to CI.

Run both candidates on the same dataset and grader. Report regressions as well
as improvements. A change to labels or grading rules creates a new test; it is
not evidence that the old candidate got better.

Local profiles, reports, caches, and environment files are ignored. Recorded
portfolio evidence and intentional documentation screenshots are reviewed artifacts.
Review an exported profile before sharing it: it includes all of your inputs
and expected answers.

Contributions are distributed under the project’s [MIT-0 license](LICENSE).
Submit only material you have authority to contribute. Third-party data retains
its own license and must have a source record and notice; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
