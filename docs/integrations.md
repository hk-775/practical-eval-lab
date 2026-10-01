# Bring your application

A candidate receives only a case's `input`. References, tags, IDs, and human labels
remain with the runner. Return a JSON-serializable output matching the selected
suite. The runnable demos intentionally call a tiny rules application so the
integration can be verified without a provider account.

## Python callable

Start with the included complete example:

```bash
uv run --locked eval-lab compare --suite classification \
  --project examples/python-project.json --before app-v1 --after app-v2
uv run --locked eval-lab serve --project examples/python-project.json
```

Replace `eval_lab.demo_app:classify_ticket` in a trusted project file with your own
installed `module:function`. Optional `options` become keyword arguments; `suites`
limits which tasks the registration may run. Project schema version is 1.

```json
{
  "schema_version": 1,
  "candidates": {
    "my-application": {
      "kind": "python",
      "target": "my_package:answer",
      "options": {"version": "v2"},
      "suites": ["classification"]
    }
  }
}
```

Install your application into the same environment. Source-only modules can be
made importable through your normal Python packaging or PYTHONPATH workflow. No
arbitrary filesystem import path is accepted from the webpage.

For direct Python integration, no project file is needed:

```python
from eval_lab.core import run_eval
from eval_lab.integrations import CandidateOutput


def evaluate_ticket(text):
    # Replace with your application call. Token usage is optional.
    return CandidateOutput("Other", usage={})


report = run_eval("classification", runner=evaluate_ticket, trials=2)
```

Use `CandidateOutput` only when supplying token counts or model metadata. A raw
dict remains an ordinary candidate output; extraction objects are never confused
with an adapter envelope. Supported usage keys are `input_tokens`, `output_tokens`,
and `total_tokens`, with nonnegative integer values. Optional metadata preserves
`model` and `response_id`. Reports never infer missing usage or billing.

## HTTP application

In terminal one:

```bash
uv run --locked python -m eval_lab.demo_app --port 8765
```

In terminal two:

```bash
uv run --locked eval-lab compare --suite classification \
  --project examples/http-project.json --before endpoint-v1 --after endpoint-v2
uv run --locked eval-lab serve --project examples/http-project.json
```

The adapter sends a POST with `{"input": ...}` and expects
`{"output": ...}`, optionally with `usage` and `metadata`. It has a configurable
1–120 second timeout (fractional positive seconds also work), a 2 MB response
limit, and no retries or redirects. Remote endpoints require HTTPS; HTTP is
allowed only for loopback hosts. URL credentials, query strings, and fragments
are rejected. To authenticate, set `token_env` to an environment-variable name;
its value is sent as a Bearer token and is not copied into the report.

Candidate exceptions become failed executions with the exception type only.
Inspect your application's own protected logs for detailed errors. Reports still
contain inputs and outputs, so review them before sharing.

## Optional OpenAI judge

Choose a model explicitly and set `OPENAI_API_KEY` in your environment or secret
manager. A live run sends inputs to the provider and may incur costs.

```bash
uv sync --locked --extra openai
uv run --locked --extra openai eval-lab run --suite response_quality \
  --candidate openai --model YOUR_MODEL --trials 3 \
  --report reports/live-judge.json --html reports/live-judge.html
```

`YOUR_MODEL` is a placeholder, not a claimed available model. Use `--prompt FILE`
to replace the suite prompt. The adapter uses the Responses API, records the
requested model, prompt, returned model identifier, response ID, and token usage.
Each call has a 30-second timeout and zero automatic retries. Output parsing is
strict: Markdown fences around JSON fail the relevant JSON grader.

To compare prompts or models, register two `kind: "openai"` candidates with
explicit `model`, optional `prompt`, and `suites`, then use `compare --project`
with `--before` and `--after`. The webpage refuses direct OpenAI registrations;
run live-model experiments through the CLI. Registered HTTP/Python applications
can themselves use paid services, so choose those registrations deliberately.

The offline pairwise example measures heuristic agreement with real human labels.
No paid model judge run or model performance result is bundled.

## Execution boundaries

A project file is trusted code/network configuration, not an untrusted tuning
profile. Loading a Python candidate executes its module. Functions run sequentially
in-process; Python candidates have no forced timeout or cancellation. Keep runs
small and use your application's own request limits. The browser disables controls
while a run is active. Distributed workers, resumability, and live job cancellation
are outside this portfolio's implemented scope.

The server binds only to loopback and has no multi-user authentication. Do not
expose it as a public application. Credentials never belong in project options,
cases, profiles, output text, or source control.
