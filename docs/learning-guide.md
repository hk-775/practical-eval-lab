# Run → inspect → change → compare

An eval is a repeatable experiment: a dataset, a candidate, a grader, and a
decision rule. This lab makes each part visible.

## 1. Classification: read failures before improving rules

Start the webpage with `uv run --locked python server.py`, choose Classification,
and click **Compare candidates**.

The baseline passes 14 of 20 development cases. The improved rules pass 20.
Filter to **Changed results** and inspect the Spanish ticket and procurement
requests. The improvement comes from a small vocabulary extension and checking
business requests before hardware keywords.

Now choose Holdout. The improved rules pass only 7 of 10. They miss unfamiliar
vocabulary and another language. Development success does not prove broad
language understanding.

The original 15-case starter is preserved in root `cases.jsonl`:

```bash
uv run --locked python eval.py --cases cases.jsonl
```

That original baseline still passes 13/15.

## 2. Extraction: separate formatting from meaning

Choose Structured extraction. A response must include:

```json
{"order_id":"A-104","quantity":3,"item":"keyboard","priority":"normal"}
```

The grader checks that the output is an object, fields have the right types,
and each field matches the reference. `true` is not a valid quantity, even
though Python treats booleans as a numeric subtype. JSON with the wrong quantity
still fails.

Inspect the **not urgent** case. The baseline sees `urgent` and assigns high
priority. The improved rules recognize the negation and assign low priority.
This suite defines “not urgent” and “no rush” as low priority. That convention
is part of this example's task contract, not a universal business rule.

Toggle **Allow extra fields** to change the schema rule. Required fields and
their values remain checked. The current local candidates do not add extra
fields, so this setting may leave their scores unchanged.

The improved rules still miss `six` and `printers` in holdout. Adding cases is
useful only when their reference answers reflect the actual task.

## 3. Tool calling: improvement can include regressions

Choose Tool calling, then Holdout, then compare. The score improves from 50% to
80%, but one case regresses: “Could you locate A-104?”

The baseline looks up any mentioned order number. This answers that case
correctly but also acts on cancellation requests and illustrative IDs. The
improved candidate requires a recognized status-query phrase. It rejects more
inappropriate actions, but does not recognize “locate.”

Filter to **Regressions**. The useful question is not only “did the average go
up?” but also “which behavior did we lose?”

The tools never contact real services:

- `lookup_order(order_id)` reads three synthetic order statuses.
- `create_ticket(category, summary)` returns a simulated outcome.
- `no_action()` records that nothing should happen.

There is no autonomous agent loop. This suite tests a single tool decision,
its arguments, and the simulator's result.

## 4. Tune an eval in the webpage

1. Choose Development and select a case.
2. Edit its input, expected answer, or tags. For extraction and tools, the expected
   answer must be a JSON object matching the suite contract.
3. Apply the case to the draft. Running, saving, and exporting also apply pending
   case edits and validate them.
4. Adjust grading settings or the passing threshold.
5. Rerun both candidates. The comparison uses the same edited data for both.
6. Save tuning to keep it across reloads. Export a profile to share or use in CLI.

Add case duplicates the selected example into a new `custom-N` case so you can
adapt a valid reference. Remove case affects only the development draft.

Saved overrides live in `local/profiles/`; earlier saved versions are in
`local/history/`. Restore defaults archives the saved version and returns to
the bundled cases. Unsaved drafts are not persisted across closing the page.
Concurrent saves detect stale versions instead of overwriting another tab's work.

Exported profiles can be imported back into the same suite. A profile contains
all case text; use synthetic or otherwise shareable inputs.

```bash
uv run --locked python -m eval_lab compare \
  --suite extraction --config extraction-profile.json \
  --report reports/my-comparison.json
```

The CLI does not silently load local webpage overrides. Pass `--config` explicitly.
Holdout uses the bundled grader settings and 80% gate in the webpage. Your
development draft remains available when you switch back.

## 5. Keep the experiment honest

Changing the passing threshold changes only the gate. Changing labels, cases,
or grading rules changes the test. Reports record hashes of the dataset and
grader; comparisons reject mismatched configurations.

Pass rate is the fraction of cases passing **every** enabled check. Slice scores
show the numerator and denominator because these samples are tiny. Tags overlap;
their totals should not be added together.

The original three suites contain 90 synthetic teaching examples. Both rule candidates
were developed for this lab. Holdout is a reserved teaching split in a public
repository, not a secret benchmark or a guarantee against contamination.
The guide discusses its failures openly. For a real product, collect a larger,
representative dataset and reserve fresh examples before tuning.

Continue with the [RAG](../examples/rag.md), [response-quality](../examples/response-quality.md), and [agent](../examples/agent.md) walkthroughs. They separate evidence, human agreement, and workflow completion. Inspect saved runs, measurement details, and standalone HTML exports in the webpage.

Do not use exact text equality as a general judge of open-ended quality. The RAG grader is explicitly extractive; the response-quality example uses real human preferences with documented limitations.
