# Dataset provenance

The first three suites contain 90 synthetic cases retained from the original lab.
RAG and multi-step agents add 24 synthetic cases. These 114 cases use invented
support tickets, orders, policies, and tool results. Their references were authored
as part of the teaching task, not collected from model users or production systems.
Original project code and these synthetic cases use MIT-0.

## Human-preference calibration sample

Response quality uses **12 existing human-preference pairs** from
[Anthropic HH-RLHF](https://github.com/anthropics/hh-rlhf), revision
`c72f5cee8eb7b4d2ea5617657f4430d5e333af07`, file
`helpful-base/test.jsonl.gz`. The source describes `chosen`/`rejected` responses
ranked through human preference collection. It does not supply this project's
rubric scores; we do not invent those scores or call heuristic labels human.

[Dataset description](https://github.com/anthropics/hh-rlhf/blob/c72f5cee8eb7b4d2ea5617657f4430d5e333af07/README.md) ·
[Upstream license](https://github.com/anthropics/hh-rlhf/blob/c72f5cee8eb7b4d2ea5617657f4430d5e333af07/LICENSE) ·
[Included MIT notice](../eval_lab/data/response_quality/LICENSE.txt) ·
[Per-record manifest](../eval_lab/data/response_quality/provenance.json)

Selection: short, everyday-topic conversations were manually inspected for this
small demonstration. Selection was purposeful, not random or representative.
The local dev lines are 18, 68, 104, 137, 148, and 354. Local holdout lines are 535,
595, 603, 53, 384, and 397. Both local splits come from the upstream test file;
“holdout” here means reserved from local tuning, not Anthropic's original train/test
partition or a hidden benchmark.

Transformation: split each `chosen` and `rejected` string at its last
`\n\nAssistant:` marker; require identical preceding conversation; retain exact
conversation and response substrings, including whitespace. Alternate the original
human-preferred response between A and B within each local split. Only the
reference contains the winner; the candidate receives conversation, A, and B.
The manifest includes each original record's SHA-256 and 1-based source line.

The original preference is not a certificate of correctness. For example, the
circle-area pair contains a questionable preferred response; its original label
is preserved and tagged `noisy-reference`. Review disagreements rather than
assuming the human reference or automated judge is always right. The original
larger dataset contains sensitive material; only these inspected pairs are bundled.

These texts and reproductions in recorded reports retain Anthropic's MIT license,
including attribution. JSON/HTML response-quality exports carry that notice too.
When adapting or editing cases, retain applicable notices and document provenance
for any new data. Changing a reference after examining results invalidates claims
that the new score measures the same test.

## How to use these datasets responsibly as experiments

The candidates were authored for this lab, and the walkthroughs openly discuss
holdout failures. The data is educational and small. It does not establish general
model quality, real-world safety, fairness, or resistance to contamination. For a
real application, define the target population and risk categories, obtain properly
licensed or consented examples, adjudicate ambiguous labels, and reserve fresh data
before tuning. Repeated runs of the same case measure variability, not new coverage.

The optional `examples/incidents/rag-profile.json` adds four explicitly fictional
MIT-0 exercises outside the six-suite case counts. Incident documentation paraphrases
public primary sources and links the original accounts; it does not redistribute
full articles, customer transcripts, or the affected systems.

## Subscription workflow regression cases

`benchmarks/subscription_workflow/data/` contains 120 original MIT-0 synthetic
episodes outside the six teaching suites: 40 development, 40 calibration, and 40
frozen test episodes. Each partition covers 20 engineering conditions, with two
parameter variants. No customer, employer, production, or incident transcript was
used. The IDs, approvals, money, and provider faults are invented.

Partitions have different parameters and wording but share authored scenario
templates. The recordings compare deterministic control profiles, with no model
or production service executed. Counts describe regression coverage, not model
generalization or real-world incident rates. See the
[subscription protocol](../benchmarks/subscription_workflow/PROTOCOL.md).
