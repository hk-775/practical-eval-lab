# Support

Start with the [quickstart](README.md), [walkthroughs](README.md#choose-a-lesson),
and [integration guide](docs/integrations.md). For a reproducible issue, include
a synthetic example, suite/candidate, and command or browser steps. Once published,
use the repository's issue tracker. There is no support SLA or production certification.

| Symptom | What to check |
|---|---|
| Command exits 1 | A quality gate failed. Several baseline/holdout failures are intentional; inspect the report. |
| Command exits 2 | Read the configuration or file error. Use matching suite/profile versions and compatible reports. |
| Command exits 3 | A candidate execution failed. The report shows the exception type; check protected application logs. |
| Port already in use | Start `eval-lab serve --port 8766` or stop your previous local server. |
| Optional OpenAI adapter missing | Run `uv sync --locked --extra openai` and run with that extra enabled. |
| Missing model/key | Choose a model explicitly and set OPENAI_API_KEY in your environment. No key is needed offline. |
| Python candidate cannot import | Install its module into the same environment; confirm module:function and suites registration. |
| Saved report will not compare | Rerun both candidates against the same cases, grader, threshold, trial count, and gate policy. |
| Old JSON report will not import | Run it again with report schema version 2. Legacy tuning profiles still import. |
| Saved profile differs between tabs | Reload the latest revision before saving; stale writes are rejected. |
| Installed app cannot write state | Set EVAL_LAB_HOME or use --state-dir with a writable local directory. |

After dependencies and Python are installed, default examples and the webpage
operate offline. A dependency-free source run (`python -m eval_lab serve`) needs
no dependency download. The first `uv sync`, build, or optional-provider setup can
need network access unless its dependencies are already cached.
