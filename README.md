# Practical Eval Lab

Learn evaluation by running a test, inspecting its failures, changing one thing,
and comparing the results. Three small suites share a Python runner and a local
webpage where you can tune cases, expected answers, grading rules, and thresholds.

**Status:** educational starter, licensed under [MIT-0](LICENSE). The default
candidates are transparent rules, and all bundled data is synthetic. No API key
is needed for the webpage.

## Start the webpage

Python 3.10+ and [uv](https://docs.astral.sh/uv/) are required for the locked workflow.
From the project directory:

```bash
uv sync --locked
uv run --locked python server.py
```

Open <http://127.0.0.1:8000>. Stop with Ctrl+C. If that port is occupied:

```bash
uv run --locked python server.py --port 8765
```

The dependency-free local runner also supports `python3 server.py` and
`python3 eval.py` for the original starter workflow. Use the locked commands for
contributions and reproducible checks.

The webpage lets you:

- Run classification, structured extraction, and simulated tool-calling evals.
- Compare the baseline and improved rules on identical cases.
- Filter failures, changed results, and regressions; inspect each grader check.
- Edit, add, and remove development cases; adjust settings and the passing gate.
- Save profiles locally, restore defaults, and import/export JSON profiles.
- Download reports with the configuration and dataset/grader fingerprints.
- Run a separate reserved holdout set with its original configuration.

See the [guided learning exercises](docs/learning-guide.md).

## The three suites

| Suite | Question | Grader | Development cases | Holdout cases |
|---|---|---|---:|---:|
| Classification | Is a support ticket Hardware, Software, or Other? | Label match | 20 | 10 |
| Structured extraction | Did we extract the order fields correctly? | JSON schema and field values | 20 | 10 |
| Tool calling | Did we select the right tool and arguments? | Call validation and simulated outcome | 20 | 10 |

The improved rules pass all development examples but still fail holdout cases.
That gap is intentional teaching material, not evidence of general model quality.
These small authored datasets are not a production benchmark.

## Run from the command line

```bash
uv run --locked python -m eval_lab run --suite classification
uv run --locked python -m eval_lab compare --suite extraction
uv run --locked python -m eval_lab compare --suite tool_calling --split holdout
uv run --locked python -m eval_lab run --suite classification \
  --candidate improved --report reports/classification.json
```

Exit status is `0` when the evaluated candidate clears the gate, `1` when it
fails, and `2` for invalid configuration. For `compare`, the improved candidate's
gate determines the exit status; regressions are reported separately.

Run a profile exported by the webpage:

```bash
uv run --locked python -m eval_lab compare --suite extraction \
  --config extraction-profile.json --report reports/comparison.json
```

Webpage saves live in ignored `local/profiles/`, with older saved versions in
`local/history/`. The CLI uses bundled data unless you explicitly pass `--config`
or `--cases`. Restoring defaults preserves saved history but discards unsaved edits.

## Evaluate your own function

```python
from eval_lab.core import run_eval


def my_classifier(ticket):
    return "Other"  # Replace with your application call.


report = run_eval("classification", runner=my_classifier)
print(report["score"])
```

Custom cases are lists of `{id, input, expected, tags}` dictionaries. JSONL files
use one such object per line. The suite validates expected answers before running.
A candidate error always fails its case, and the remaining cases still run.

## Optional live model evaluation

The existing OpenAI adapter is available through the CLI only. Set
`OPENAI_API_KEY` through your environment or secret-management workflow; never
put a key in source, profiles, reports, or the browser. Choose your model explicitly.
Live runs send case inputs to the provider and may incur API costs.

```bash
uv sync --locked --extra openai
uv run --locked --extra openai python -m eval_lab run \
  --suite extraction --candidate openai --model YOUR_MODEL \
  --report reports/live-extraction.json
```

Use `--prompt path/to/prompt.txt` to override the suite's instructions. Reports
record the prompt and requested model. Live model output may vary between runs;
record repeated measurements when that matters. The adapter has not been exercised
with paid live calls as part of this milestone. No model quality or cost claims
are made here.

## How it fits together

![Dataset, candidate, grader, report, and local tuning profile](docs/architecture/pipeline.svg)

[Editable diagram](docs/architecture/pipeline.drawio) ·
[Publication inventory and AWS applicability decision](docs/publication.md)

Both the CLI and local webpage use the same Python validation, graders, and runner.
Matched comparisons require the same dataset, grader, split, and threshold.
The tool simulator has no network or real-world side effects.

## Verify

```bash
uv sync --locked
uv run --locked pytest -q
uv run --locked playwright install chromium
uv run --locked python -m scripts.browser_check
```

The browser check starts an isolated temporary server and verifies persistence,
import/export, filters, all suites, holdout regressions, mobile layout, and absence
of external network requests or WebSockets. CI installs Chromium's Linux dependencies
with `playwright install --with-deps chromium`.

[Contributing](CONTRIBUTING.md) · [Support](SUPPORT.md) ·
[Security](SECURITY.md) · [Community conduct](CODE_OF_CONDUCT.md)

## License

[MIT No Attribution (MIT-0)](LICENSE).
