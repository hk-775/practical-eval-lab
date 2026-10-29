"""Offline presentation of the expanded experiment, with explicit sampling units."""

from __future__ import annotations

import html
import json

from benchmarks.recursive_improvement.artifacts import ROOT as V1_ROOT, verify_seal
from benchmarks.recursive_improvement.reporting import workflow_svg

from .data import ROOT
from .engine import ARMS
from .diagnostics import analyze

LABELS = {"fixed_agent": "Fixed agent", "random_search": "Random search",
          "fixed_optimizer": "Fixed optimizer", "recursive_optimizer": "Recursive optimizer"}
COLORS = {"fixed_agent": "#697786", "random_search": "#80634a",
          "fixed_optimizer": "#0D1B2A", "recursive_optimizer": "#007B95"}


def rate(counts, key="task_success", denominator="episodes"):
    return counts[key] / counts[denominator] if counts[denominator] else 0


def interval_text(pair):
    interval = pair["percentile_bootstrap_95"]
    return ("insufficient seeds" if interval is None else
            f"{interval[0] * 100:+.2f} to {interval[1] * 100:+.2f} percentage points")


def verdict(report):
    pair = report["paired"]["recursive_optimizer"]
    return (
        f"Recursive versus fixed optimizer: {pair['mean_success_rate_difference'] * 100:+.2f} "
        f"percentage points in mean final correct handling. Across {pair['paired_seed_count']} "
        f"paired seeds: {pair['wins']} wins, {pair['ties']} ties, {pair['losses']} losses. "
        f"95% paired-seed bootstrap interval: {interval_text(pair)}."
    )


def check(report):
    verify_seal(report)
    if report.get("kind") != "bounded-rsi-v2-evaluation":
        raise ValueError("Expected a v2 evaluation")


def markdown(report):
    check(report)
    rows = ["# Expanded bounded RSI evaluation", "", report["notice"], "", verdict(report), "",
            "## Final results", "",
            "| Arm | Correct handling | Business completion | Unsafe effects | Provider calls per case |",
            "|---|---:|---:|---:|---:|"]
    for arm in ARMS:
        counts = report["aggregate"][arm]
        rows.append(f"| {LABELS[arm]} | {rate(counts):.2%} "
                    f"| {rate(counts, 'business_completed', 'business_required'):.2%} "
                    f"| {counts['unsafe_effects']} | {counts['provider_calls']/counts['episodes']:.2f} |")
    reference = report["reference"]["counts"]
    diagnostic = analyze(report)
    bounds = diagnostic["paired_seed_percentile_95"]
    rows += [
        "", f"Predeclared hand-written reference: {reference['task_success']}/{reference['episodes']} "
        f"correctly handled ({rate(reference):.2%}). It is outside the matched search budget.",
        "", "## Exploratory comparison with random search", "",
        f"Recursive minus random: {diagnostic['mean_success_rate_difference'] * 100:+.2f} percentage points.",
        ("Paired-seed 95% percentile interval: "
         f"{bounds[0] * 100:+.2f} to {bounds[1] * 100:+.2f} percentage points."
         if bounds else "Too few seeds for the interval."),
        "This comparison was added after inspecting results. It is exploratory, not preregistered.",
        "The fixed heuristic repeatedly targets previously repaired scope errors in compound",
        "failure traces. Its low score is a limitation of this baseline; the larger margin",
        "against it does not establish a general advantage for recursive improvement.",
        "", "The fixed final corpus has 1,212 scenarios in 303 semantic composition families.",
        "Four parameter variants per family and repeated seeds are correlated. Bootstrap",
        "intervals resample paired search seeds only, conditional on this synthetic corpus.",
        "They do not describe independently sampled enterprise or scenario-family uncertainty.",
        "", "## Design", "",
        "Development: 360 cases / 180 families. Validation: 306 cases / 153 families.",
        "Previously exposed v1 families are development-only. All partitions include the",
        "supported transient outage depths and persistent failures. Four-failure scenarios",
        "exceed this policy language's three-retry limit and remain in the denominator.",
        "", "Validation examines every proposal after search ends, including development-rejected",
        "proposals. The selected set is committed before final cases are evaluated.",
        "", "## Work and evidence", "",
        f"- Logical search requests: {report['search']['state']['evaluation_requests']:,}.",
        f"- Distinct policy/case executions in search: "
        f"{report['search']['state']['physical_search_episodes']:,}.",
        f"- Distinct policy/case executions including final and reference: "
        f"{report['physical_total_episodes']:,}.",
        "- Cache hits spend the same logical allowance. These are not matched CPU-time or token budgets.",
        "- The common fixed guard protects every arm; zero violations do not demonstrate learned authorization.",
        "- Compact batches retain every case's counts and complete-trace hash. `inspect` reconstructs",
        "  a full trace and verifies that commitment; `audit` reconstructs the whole experiment.",
        f"- Protocol SHA-256: `{report['protocol_hash']}`",
        f"- Report SHA-256: `{report['sha256']}`",
        f"- Selected-set SHA-256: `{report['search']['selection_commitment']}`",
        f"- Recorded UTC: `{report['created_at']}`",
        f"- Source revision: `{report['source']['revision']}`; dirty: `{report['source']['worktree_dirty']}`.",
        "", "This revision changes both case coverage and candidate selection; score differences",
        "from v1 cannot be attributed to sample size alone. No model was trained or invoked.",
        "The author, provider model and fault vocabulary remain shared. No artifact is deployed.", "",
    ]
    return "\n".join(rows)


def chart(report):
    runs = report["search"]["state"]["runs"]
    generations = report["search"]["state"]["plan"]["generations"]
    parts = ['<svg class="chart" viewBox="0 0 960 250" role="img" '
             'aria-label="Mean development correct handling across search seeds">']
    for value in (0, 50, 100):
        y = 210 - value * 1.7
        parts.append(f'<path class="grid" d="M55 {y} H920"/>'
                     f'<text x="45" y="{y+5}" text-anchor="end">{value}%</text>')
    for arm in ARMS:
        matching = [run for run in runs if run["arm"] == arm]
        points = []
        for generation in range(generations + 1):
            mean = sum(rate(run["checkpoints"][generation]["development"])
                       for run in matching) / len(matching)
            points.append(f"{55 + 865 * generation/generations:.2f},{210 - 170*mean:.2f}")
        parts.append(f'<polyline points="{" ".join(points)}" fill="none" '
                     f'stroke="{COLORS[arm]}" stroke-width="3"><title>{LABELS[arm]}</title></polyline>')
    for generation in range(generations + 1):
        parts.append(f'<text x="{55+865*generation/generations}" y="237" '
                     f'text-anchor="middle">{generation}</text>')
    return "".join(parts) + "</svg>"


def render_html(report):
    check(report)
    esc = html.escape
    runs = report["search"]["state"]["runs"]
    settings = report["search"]["state"]["plan"]
    table = []
    for arm in ARMS:
        counts = report["aggregate"][arm]
        values = [LABELS[arm], f"{rate(counts):.2%}",
                  f"{rate(counts, 'business_completed', 'business_required'):.2%}",
                  str(counts["unsafe_effects"]),
                  f"{rate(counts, 'human_interventions'):.2%}",
                  f"{counts['provider_calls']/counts['episodes']:.2f}"]
        table.append("<tr>" + "".join(f"<td>{esc(value)}</td>" for value in values) + "</tr>")
    pair_rows = []
    for arm, pair in report["paired"].items():
        pair_rows.append(f"<tr><td>{LABELS[arm]}</td>"
                         f"<td>{pair['mean_success_rate_difference']*100:+.2f} pp</td>"
                         f"<td>{interval_text(pair)}</td>"
                         f"<td>{pair['wins']} / {pair['ties']} / {pair['losses']}</td></tr>")
    seed_options = "".join(f'<option value="{seed}">{index+1} · {seed}</option>'
                           for index, seed in enumerate(settings["seeds"]))
    arm_options = "".join(f'<option value="{arm}">{LABELS[arm]}</option>' for arm in ARMS)
    reference = report["reference"]["counts"]
    diagnostic = analyze(report)
    bounds = diagnostic["paired_seed_percentile_95"]
    exploratory_interval = ("insufficient seeds" if bounds is None else
                            f"{bounds[0]*100:+.2f} to {bounds[1]*100:+.2f} percentage points")
    logical_episodes = sum(row["budget"]["logical_development_episodes"]
                           + row["budget"]["logical_validation_episodes"] for row in runs)
    requests_per_split = 1 + 2 * settings["generations"]
    payload = json.dumps({"runs": runs}, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    css = (V1_ROOT / "viewer.css").read_text(encoding="utf-8")
    js = (ROOT / "viewer.js").read_text(encoding="utf-8")
    legend = " ".join(f'<span style="color:{COLORS[arm]}">— {LABELS[arm]}</span>' for arm in ARMS)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Expanded RSI evaluation · Practical Eval Lab</title><style>{css}</style></head>
<body><a class="skip" href="#main">Skip to evidence</a>
<header><p class="eyebrow">Practical Eval Lab · Bounded RSI v2</p>
<h1>More coverage.<br>A stronger comparison.</h1>
<p class="intro">A larger experiment in workflow recovery, with grouped scenarios,
all-proposal validation, and paired search seeds.</p>
<p class="tag">Synthetic workloads · Finite configuration search · No model calls</p></header>
<main id="main"><section><h2>What the final evaluation found</h2>
<p class="finding">{esc(verdict(report))}</p>
<div class="stats"><div><strong>1,212</strong><span>final scenarios</span></div>
<div><strong>303</strong><span>final composition families</span></div>
<div><strong>{len(settings['seeds'])}</strong><span>paired search seeds</span></div></div>
<div class="table-scroll"><table id="results"><caption>Means across seeds on the same final corpus</caption>
<thead><tr><th>Arm</th><th>Correct handling</th><th>Business completion</th><th>Unsafe effects</th>
<th>Human intervention</th><th>Provider calls / case</th></tr></thead><tbody>{"".join(table)}</tbody></table></div>
<p class="small">Correct handling includes clarification and truthful handoff. Persistent outages remain
in the business-completion denominator. Zero observed unsafe effects apply to the shared fixed guard.</p>
<div class="budget"><strong>Exploratory comparison with random search:</strong>
recursive search gained {diagnostic["mean_success_rate_difference"]*100:+.2f} percentage points;
the paired-seed 95% interval is {exploratory_interval}. This comparison was added after
inspecting the result. The fixed heuristic repeatedly targets scope errors already repaired
earlier in a failed workflow. Its low score does not establish a general RSI advantage.</div>
<div class="budget"><strong>Predeclared engineering reference:</strong>
{reference["task_success"]}/{reference["episodes"]} correct ({rate(reference):.2%}).
This hand-written policy is outside the matched search budget. Four-failure scenarios exceed
the available three-retry policy limit.</div></section>
<section><h2>What changed from v1</h2>
<ul><li>636 total semantic fault-combination families, with variants grouped by family.</li>
<li>360 development, 306 validation and 1,212 final cases. Exposed v1 combinations stay in development.</li>
<li>All proposals reach validation after search, including those rejected during development.</li>
<li>Four comparison arms, including uniform random search, across paired seeds.</li></ul>
<p>Both coverage and selection changed. A v1-to-v2 score difference cannot be attributed to sample size alone.</p>
<div class="section-heading"><h2>The bounded improvement loop</h2>
<button id="motion" type="button" hidden aria-pressed="false">Pause motion</button></div>
<div id="diagram" class="diagram-scroll">{workflow_svg()}</div>
<p class="small">Motion illustrates flow. It does not represent timing or live execution.
Authorization, scoring, the final cases and release controls remain outside the editable configuration.</p></section>
<section><h2>Uncertainty across search seeds</h2>
<div class="table-scroll"><table><thead><tr><th>Versus fixed optimizer</th><th>Mean difference</th>
<th>95% paired-seed bootstrap interval</th><th>Wins / ties / losses</th></tr></thead>
<tbody>{"".join(pair_rows)}</tbody></table></div>
<p>Intervals resample entire paired seeds, conditional on this fixed synthetic corpus.
They do not describe production uncertainty or independent scenario-family sampling.
The four variants within each family and repeated seed outcomes are correlated.</p></section>
<section><h2>Development progress and candidate selection</h2>
<div class="chart-scroll">{chart(report)}</div><p class="legend">{legend}</p>
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
<noscript><p>Summary tables and development curves remain available without JavaScript.
The comparison JSON and compressed evidence batches contain the full search record.</p></noscript>
<p class="small">Navigation shows incumbents; “Show selected proposal” displays the actual
validation choice, which can be a development-rejected proposal. Selection finishes before final testing.</p></section>
<section><h2>Work, evidence and limits</h2>
<p>{esc(report["notice"])}</p>
<p>Each arm and seed receives {requests_per_split} development and {requests_per_split} validation requests.
This run represents {logical_episodes:,} logical development/validation episodes.
Cache hits spend the same allowance and contribute the same simulated provider work.</p>
<p><strong>{report["physical_total_episodes"]:,}</strong> distinct policy/case executions
were physically performed across search, validation, final evaluation and the reference.
Replay and audit execute additional verification work.</p>
<p>Compact evidence retains each case's independent counts and a hash of its complete trace.
The inspect command reconstructs a full trace and checks the original commitment.
Audit reconstructs search, selection, outcomes and comparisons.</p>
<p>The author, provider model and primitive fault vocabulary remain shared.
The public test is author-visible. No language model or production traffic was evaluated.</p>
<details><summary>Evidence identity</summary><dl>
<dt>Report</dt><dd>{report["sha256"]}</dd>
<dt>Protocol</dt><dd>{report["protocol_hash"]}</dd>
<dt>Selected set</dt><dd>{report["search"]["selection_commitment"]}</dd>
<dt>Recorded UTC</dt><dd>{report["created_at"]}</dd>
<dt>Source revision</dt><dd>{report["source"]["revision"]}</dd>
<dt>Working tree contained changes when recorded</dt><dd>{report["source"]["worktree_dirty"]}</dd>
</dl><p>Hashes identify content; they are not signed attestations. Nothing is deployed.</p></details></section>
<footer>Original code and synthetic cases: MIT-0 · Practical Eval Lab<br>
This offline viewer makes no external requests.</footer></main>
<script type="application/json" id="evidence">{payload}</script><script>{js}</script></body></html>"""
