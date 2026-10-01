# Data, candidates, grades, and reports

## Case

A JSONL dataset contains 1–500 objects with exactly `id`, `input`, `expected`, and
`tags`. IDs are unique nonempty strings up to 100 characters. Inputs fit within
20,000 serialized characters. Tags are up to 20 distinct nonempty strings of at
most 60 characters. JSON numbers must be finite.

The first three examples use string inputs. RAG, pairwise judging, and agents use
structured objects. Each suite validates both its input and reference contract
before a candidate runs. `eval_lab/data/<suite>/{dev,holdout}.jsonl` contains concrete
examples. RAG references must quote an existing current, trusted relevant document.

## Candidate and grade

Built-ins are `baseline` and `improved`; `openai` is an optional CLI adapter.
Trusted project registrations add named Python, HTTP, or OpenAI candidates.
A candidate receives a deep copy of the input, never the reference. Return a JSON
value or `CandidateOutput(output, usage, metadata)` as described in the
[integration guide](integrations.md).

A grader returns `passed`, nonempty `checks` with `name`, boolean `passed`, and
human-readable `detail`, plus optional numeric `metrics`. A case passes only if
every enabled check passes. Exceptions fail execution and are counted separately.

Classification, extraction, and one-call tools are in `suites.py`; the new tasks
are in `advanced.py`. To add a suite, register its metadata and settings, implement
input/reference validation, a grader, and local candidates, and add separate dev
and holdout files. Cover meaningful negative examples in tests. This is an
explicit teaching catalog, not a dynamic untrusted-grader plugin system.

## Tuning profile, version 2

```json
{
  "schema_version": 2,
  "suite": "classification",
  "cases": [{"id":"example", "input":"My keyboard is broken", "expected":"Hardware", "tags":["critical"]}],
  "settings": {"normalize_labels": true},
  "threshold": 0.8
}
```

Legacy three-field profiles (`cases`, `settings`, `threshold`) are accepted and
normalized to version 2. Current profiles include suite identity to reject an
accidental cross-suite import. Save revisions detect stale browser edits, and
prior saved versions are archived before replacement or reset.

## Run report, version 2

Reports record suite, split, candidate identity, lab version, timestamp, dataset
and grader hashes, threshold, settings, gate policy, results, slices, errors,
trials, case count, and derived measurements. Repeated execution IDs append a
trial suffix; `case_id` retains the original identity. Both candidate and grader
latency are recorded, while token usage is present only when actually supplied.

Candidate source/configuration fingerprints identify the local implementation or
registration without copying secret environment values. Grader fingerprints cover
the shared runner and grader source plus settings. They do not fingerprint your
external service or prove which remote deployment answered; version that service
and its candidate configuration explicitly.

Derived check and measurement rates report their denominators. An execution error
may have only an execution check, so a per-field or per-metric rate can describe
fewer outputs than the entire dataset. Overall pass rate always includes errors.
The report includes total errors and usage coverage to make this visible.

Matched comparison requires identical schema, suite, split, dataset hash, grader
hash, threshold, trial count, and gate policy, plus the same execution IDs. It
reports per-execution improvements/regressions, delta, and gate results. A total
score increase does not override a regression or critical-case gate.

Reports import up to 20 MB. Validation checks structures, counts, fingerprints
against embedded cases, trial completeness, slices, and gate consistency. Derived
measurements are recomputed. This is integrity checking, not a digital signature
or proof that a run happened. Imported evidence remains labeled, including when
it is used in a new comparison. Version 1 reports need rerunning; profile migration
is supported, but old report migration is intentionally not implied.

## Persistence and export

The local state directory contains profiles, profile history, and UUID-named run
JSON files. The UI lists the latest 200 runs; older files are retained. Export JSON
to preserve machine-readable results and HTML for a standalone readable artifact.
HTML escapes every output, contains no scripts, and loads no external assets.
Both formats include data-license notices. Neither anonymizes case contents.

Source checkouts use `local/`; installed applications use the operating system's
per-user application-data directory. `--state-dir` or `EVAL_LAB_HOME` overrides it.
Deleting an exported file does not delete saved server state.
