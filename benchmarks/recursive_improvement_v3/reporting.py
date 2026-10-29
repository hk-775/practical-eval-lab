"""Self-contained recorded results with category denominators and inherited viewer."""

from __future__ import annotations

import html
import json

from markdown import markdown as render_markdown

from benchmarks.recursive_improvement.artifacts import ROOT as V1_ROOT, verify_seal
from benchmarks.recursive_improvement.reporting import workflow_svg
from benchmarks.recursive_improvement_v2.data import ROOT as V2_ROOT
from benchmarks.recursive_improvement_v2.reporting import COLORS, LABELS, chart, interval_text, rate

from .engine import ARMS


def check(report):
    verify_seal(report)
    if report.get("kind") != "bounded-rsi-v3-evaluation":
        raise ValueError("Expected a v3 evaluation")


def verdict(report):
    pair = report["paired"]["recursive_optimizer_vs_random_search"]
    interval = pair["percentile_bootstrap_95"]
    conclusion = (
        "No clear advantage over random search is established."
        if interval is None or interval[0] <= 0 <= interval[1] else
        "Recursive search scores higher on this fixed corpus."
        if interval[0] > 0 else "Random search scores higher on this fixed corpus."
    )
    return (
        f"Recursive minus random search: {pair['mean_success_rate_difference'] * 100:+.2f} "
        f"percentage points; 95% paired-seed interval {interval_text(pair)}. {conclusion}"
    )


def markdown(report):
    check(report)
    files = report["dataset"]["files"]
    seeds = len(report["search"]["state"]["plan"]["seeds"])
    rows = [
        "# Bounded RSI v3: failures across workflow stages", "", report["notice"], "",
        "## Main comparison", "", verdict(report), "",
        "## Corpus", "",
        "| Partition | Composition families | Cases |", "|---|---:|---:|",
    ]
    for split, value in files.items():
        rows.append(f"| {split.title()} | {value['families']:,} | {value['episodes']:,} |")
    rows += [
        "", "All 636 previously exposed v2 families are development-only. The final test",
        "contains new combinations of stage outages, repeated ambiguous responses, delayed",
        "receipts, interruptions across stages, authority withdrawal and version races.",
        "Four parameter variants remain together in each final family. The author, business",
        "rules and simulator primitives are shared; this is not an independent enterprise sample.",
        "", "## Final results", "",
        "| Arm | Correct handling | Business completion | Human intervention | Unsafe effects | Provider calls / case |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        counts = report["aggregate"][arm]
        rows.append(
            f"| {LABELS[arm]} | {rate(counts):.2%} "
            f"| {rate(counts, 'business_completed', 'business_required'):.2%} "
            f"| {rate(counts, 'human_interventions'):.2%} | {counts['unsafe_effects']} "
            f"| {counts['provider_calls'] / counts['episodes']:.2f} |")
    safety = {key: sum(row[key] for row in report["aggregate"].values())
              for key in ("duplicate_refunds", "false_completion", "candidate_errors")}
    rows += [
        "", "Correct handling includes required clarification and truthful handoff with the",
        "correct committed prefix. Permanent outages and withdrawn authority remain in the",
        "business-completion denominator. All arms use the same fixed authorization guard.",
        f"Across the four arms: {safety['duplicate_refunds']} duplicate refund effects, "
        f"{safety['false_completion']} false completions and {safety['candidate_errors']} candidate errors.",
        "", "## Correct handling by failure class", "",
        "| Failure class | Final cases | Fixed agent | Random search | Fixed optimizer | Recursive optimizer |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, arms in report["slices"].items():
        count = arms["fixed_agent"]["episodes"] // seeds
        values = " | ".join(f"{rate(arms[arm]):.2%}" for arm in ARMS)
        rows.append(f"| {name.replace('_', ' ').title()} | {count:,} | {values} |")
    reference = report["reference"]["counts"]
    rows += [
        "", "The aggregate follows the authored composition distribution, not production traffic.",
        "Small temporal slices should be read with their denominators, not treated as precise estimates.",
        f"The unchanged hand-written v2 reference handled {reference['task_success']:,}/"
        f"{reference['episodes']:,} cases correctly ({rate(reference):.2%}); it is outside the search budget.",
        "", "## Registered paired comparisons", "",
        "| Comparison | Mean difference | 95% paired-seed interval | Wins / ties / losses |",
        "|---|---:|---|---:|",
    ]
    for pair in report["paired"].values():
        rows.append(
            f"| {LABELS[pair['arm']]} vs {LABELS[pair['baseline']]} "
            f"| {pair['mean_success_rate_difference'] * 100:+.2f} pp "
            f"| {interval_text(pair)} | {pair['wins']} / {pair['ties']} / {pair['losses']} |")
    logical = sum(run["budget"]["logical_development_episodes"]
                  + run["budget"]["logical_validation_episodes"]
                  for run in report["search"]["state"]["runs"])
    rows += [
        "", "Recursive versus random was registered before this run. The fixed diagnostic",
        "optimizer retains its known tendency to revisit scope errors repaired earlier in a",
        "failed episode. A large margin over that heuristic alone does not establish an RSI advantage.",
        "", "Intervals use 10,000 bootstrap resamples of entire paired search seeds. They are",
        "unadjusted descriptive intervals conditional on this fixed corpus, not production",
        "or independent-family confidence intervals. Repeated seeds and variants are correlated.",
        "", "## Work and evidence", "",
        f"- {seeds} paired seeds; eight generations; two proposals per generation.",
        "- Each arm/seed receives 17 development queries and 17 validation queries.",
        "- All proposals reach validation after search; selected identities are committed before final testing.",
        f"- Logical development/validation episodes: {logical:,}.",
        f"- Logical final episodes: {sum(row['counts']['episodes'] for row in report['runs']):,}.",
        f"- Physically executed distinct policy/case pairs: {report['physical_total_episodes']:,}.",
        "- Cache hits consume the same query allowance. CPU time, tokens and monetary cost are not matched.",
        "- The policy language, optimizers, search rules, seeds and budgets are unchanged from v2.",
        "- The corpus and provider behaviors changed; score differences are not a pure sample-size effect.",
        "- Transient faults beyond the retry cap and unsupported stale-version recovery remain in the denominator.",
        "- No language model, production provider, customer data or real money was used.",
        "- Simulated schedules advance per call. Provider latency, backoff and concurrent races are not measured.",
        "", "## Integrity", "",
        f"- Recorded UTC: `{report['created_at']}`",
        f"- Protocol SHA-256: `{report['protocol_hash']}`",
        f"- Report SHA-256: `{report['sha256']}`",
        f"- Selected-set SHA-256: `{report['search']['selection_commitment']}`",
        f"- Source revision: `{report['source']['revision']}`; working tree dirty: "
        f"`{report['source']['worktree_dirty']}`.",
        "", "Compressed evidence retains each case's outcome and complete trace commitment.",
        "`inspect` reconstructs a full trace. `audit` replays search, selection, execution,",
        "category slices and comparisons. Hashes identify content; they are not signed attestations.",
        "No candidate is deployed. Original code and synthetic cases: MIT-0.", "",
    ]
    return "\n".join(rows)


def render_html(report):
    check(report)
    settings = report["search"]["state"]["plan"]
    body = render_markdown("\n".join(markdown(report).splitlines()[1:]), extensions=["tables"])
    # Identify the arm-results table for the shared browser regression check.
    marker = "<thead>\n<tr>\n<th>Arm</th>"
    body = body.replace("<table>\n" + marker, '<table id="results">\n' + marker)
    body = body.replace("<table", '<div class="table-scroll"><table').replace("</table>", "</table></div>")
    css = (V1_ROOT / "viewer.css").read_text(encoding="utf-8")
    js = (V2_ROOT / "viewer.js").read_text(encoding="utf-8")
    seed_options = "".join(f'<option value="{seed}">{i + 1} · {seed}</option>'
                           for i, seed in enumerate(settings["seeds"]))
    arm_options = "".join(f'<option value="{arm}">{LABELS[arm]}</option>' for arm in ARMS)
    legend = "".join(f'<span style="color:{COLORS[arm]}">— {html.escape(LABELS[arm])}</span>'
                     for arm in ARMS)
    payload = json.dumps({"runs": report["search"]["state"]["runs"]},
                         separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stage fault corpus · Bounded RSI v3</title><style>{css}
code{{overflow-wrap:anywhere}}#summary h2{{margin-top:36px}}a{{color:#007B95}}
</style></head><body><a class="skip" href="#main">Skip to evidence</a>
<header><p class="eyebrow">Practical Eval Lab · Bounded RSI v3</p>
<h1>Recovery across<br>workflow stages.</h1>
<p class="intro">{report['dataset']['files']['test']['episodes']:,} final scenarios.
The same search budget. More ways for a subscription workflow to fail.</p>
<p class="tag">Synthetic workloads · Finite configuration search · No model calls</p></header>
<main id="main"><section id="summary">{body}</section>
<section><div class="section-heading"><h2>The bounded improvement loop</h2>
<button id="motion" type="button" hidden aria-pressed="false">Pause motion</button></div>
<div id="diagram" class="diagram-scroll">{workflow_svg()}</div>
<p class="small">Motion illustrates flow. It does not represent timing or live execution.
Authorization, grading and the final cases remain outside the editable configuration.</p>
<h3>Development progress</h3><div class="chart-scroll">{chart(report)}</div>
<p class="legend">{legend}</p>
<div id="controls" hidden><label>Seed <select id="seed">{seed_options}</select></label>
<label>Arm <select id="arm">{arm_options}</select></label>
<button type="button" id="previous">Previous generation</button>
<button type="button" id="next">Next generation</button>
<button type="button" id="selected">Show selected proposal</button>
<p id="position" role="status" aria-live="polite"></p></div>
<div id="inspection" hidden><p id="checkpoint"></p><div class="code-grid">
<div><h3>Workflow configuration</h3><pre id="policy"></pre></div>
<div><h3>Optimizer configuration</h3><pre id="optimizer"></pre></div></div>
<h3>Proposal details</h3><pre id="proposals"></pre></div>
<noscript><p>The summary tables and development chart remain available without JavaScript.</p></noscript>
<p class="small">Generation navigation shows incumbents. “Show selected proposal” displays
the actual validation choice, including development-rejected proposals.</p></section>
<footer>Original code and synthetic cases: MIT-0 · No external requests · Nothing deployed</footer>
</main><script type="application/json" id="evidence">{payload}</script><script>{js}</script></body></html>"""
