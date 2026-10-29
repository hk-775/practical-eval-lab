"""Self-contained evidence viewer. Rendering never reruns or rewrites a result."""

from __future__ import annotations

import html
import json
import math

from .artifacts import ARMS, ROOT, verify_seal

LABELS = {
    "fixed_agent": "Fixed agent",
    "fixed_optimizer": "Fixed optimizer",
    "recursive_optimizer": "Recursive optimizer",
}
COLORS = {"fixed_agent": "#697786", "fixed_optimizer": "#0D1B2A",
          "recursive_optimizer": "#007B95"}


def check(report):
    verify_seal(report)
    if report.get("kind") != "bounded-rsi-evaluation":
        raise ValueError("Expected a bounded RSI evaluation")
    verify_seal(report["search"])


def assessment(report):
    differences = report["comparison"]["paired_seed_differences"]
    wins = sum(row["recursive_minus_fixed_optimizer_successes"] > 0 for row in differences)
    ties = sum(row["recursive_minus_fixed_optimizer_successes"] == 0 for row in differences)
    losses = len(differences) - wins - ties
    return (f"On final correct handling, the recursive optimizer won {wins}, tied {ties}, "
            f"and lost {losses} of {len(differences)} paired seeds against the fixed optimizer. "
            "These descriptive counts apply to the specified synthetic families and search budget.")


def count(row, numerator="task_success", denominator="episodes"):
    return f"{row[numerator]}/{row[denominator]}"


def p95(runs, arm):
    values = sorted(episode["latency_ms"] for run in runs if run["arm"] == arm
                    for episode in run["episodes"])
    return values[math.ceil(len(values) * .95) - 1]


def render_markdown(report):
    check(report)
    search = report["search"]
    settings = search["state"]["plan"]
    rows = [
        "# Bounded recursive improvement: recorded results", "",
        report["notice"], "", assessment(report), "",
        f"Recorded: `{report['created_at']}`. Seeds: `{settings['seeds']}`. "
        f"Generations: {settings['generations']}.", "",
        "## Final evaluation", "",
        "| Arm | Correct handling | Business completion | Unsafe episodes | Duplicate refunds "
        "| Human intervention | Provider calls |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, result in report["comparison"]["arms"].items():
        rows.append(
            f"| {LABELS[arm]} | {count(result)} | {count(result, 'business_completed', 'business_required')} "
            f"| {count(result, 'unsafe_episodes')} | {result['duplicate_refunds']} "
            f"| {count(result, 'human_interventions')} | {result['provider_calls']} |")
    rows += [
        "", "Correct handling includes required clarification and truthful handoff. Persistent",
        "provider outages remain in the legitimate-completion denominator. The same invariant",
        "guard protects all arms; zero unsafe effects do not demonstrate learned authorization.",
        "Provider calls are simulated work, not dollar cost or model tokens.", "",
        "## Paired seeds: recursive minus fixed optimizer", "",
        "| Seed | Change in correctly handled episodes | Change in provider calls |",
        "|---|---:|---:|",
    ]
    for pair in report["comparison"]["paired_seed_differences"]:
        rows.append(f"| {pair['seed']} | {pair['recursive_minus_fixed_optimizer_successes']:+d} "
                    f"| {pair['recursive_minus_fixed_optimizer_provider_calls']:+d} |")
    rows += [
        "", "## Selected artifacts", "",
        "| Seed | Arm | Selected generation | Accepted optimizer edits during search | "
        "Selected optimizer differs from start | Artifact SHA-256 |",
        "|---|---|---:|---:|---|---|",
    ]
    for run in search["state"]["runs"]:
        rows.append(f"| {run['seed']} | {LABELS[run['arm']]} | {run['selected_generation']} "
                    f"| {run['accepted_optimizer_changes']} | {run['selected_optimizer_changed']} "
                    f"| `{run['selected_hash']}` |")
    rows += [
        "", "Selection is completed on validation before final-test execution. An accepted edit",
        "later in search may not be part of the selected earlier checkpoint.", "",
        "## Timing and identity", "",
        "p95 local simulator episode time; excludes search and contains no real provider latency:", "",
    ]
    rows += [f"- {LABELS[arm]}: {p95(report['runs'], arm):.3f} ms." for arm in ARMS]
    rows += [
        "", f"- Report: `{report['sha256']}`",
        f"- Protocol: `{report['protocol_hash']}`",
        f"- Search: `{search['sha256']}`",
        f"- Selected set: `{search['selection_commitment']}`",
        f"- Final dataset: `{report['test_dataset_hash']}`",
        f"- Source: `{report['source']['revision']}`; dirty: `{report['source']['worktree_dirty']}`.",
        "", "The committed public test is author-visible and shares an author, simulator and fault",
        "vocabulary with development. Composition separation is not independent production",
        "sampling. Repeated seeds reuse the same test cases. Preserve null and negative results.",
        "Hashes identify content; they are not authenticated attestations. Candidates are",
        "reviewable local artifacts; none is deployed by this experiment.", "",
    ]
    return "\n".join(rows)


def learning_chart(report):
    runs = report["search"]["state"]["runs"]
    generations = report["search"]["state"]["plan"]["generations"]
    parts = ['<svg class="chart" viewBox="0 0 960 250" role="img" '
             'aria-label="Development search: mean correct handling across seeds by generation">']
    for percent in (0, 50, 100):
        y = 210 - percent * 1.7
        parts.append(f'<path class="grid" d="M55 {y} H920"/>'
                     f'<text x="45" y="{y + 5}" text-anchor="end">{percent}%</text>')
    for arm in ARMS:
        matching = [run for run in runs if run["arm"] == arm]
        points = []
        for generation in range(generations + 1):
            rates = [run["checkpoints"][generation]["development"]["task_success"]
                     / run["checkpoints"][generation]["development"]["episodes"] for run in matching]
            x, y = 55 + 865 * generation / generations, 210 - 170 * sum(rates) / len(rates)
            points.append(f"{x:.2f},{y:.2f}")
        pattern = 'stroke-dasharray="7 5"' if arm == "fixed_agent" else ""
        parts.append(f'<polyline fill="none" stroke="{COLORS[arm]}" stroke-width="3" '
                     f'{pattern} points="{" ".join(points)}"><title>{LABELS[arm]}</title></polyline>')
    for generation in range(generations + 1):
        x = 55 + 865 * generation / generations
        if generations <= 12 or generation % 4 == 0:
            parts.append(f'<text x="{x}" y="236" text-anchor="middle">{generation}</text>')
    parts.append("</svg>")
    return "".join(parts)


def workflow_svg():
    nodes = [
        (20, "Observe failures"), (210, "Propose edits"), (400, "Execute"),
        (590, "Verify"), (780, "Retain version"),
    ]
    body = ['<svg class="workflow" viewBox="0 0 960 150" role="img" '
            'aria-label="Failure feedback, bounded edits, execution, fixed verification, retained version">'
            '<defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" '
            'orient="auto"><path d="M0 0 L6 3 L0 6" fill="#007B95"/></marker></defs>']
    for x, text in nodes:
        body.append(f'<rect x="{x}" y="35" width="160" height="54" rx="8"/>'
                    f'<text x="{x + 80}" y="67" text-anchor="middle">{text}</text>')
    for start in (180, 370, 560, 750):
        body.append(f'<path class="flow-line" d="M{start + 3} 62 H{start + 26}" marker-end="url(#arrow)"/>')
    body.append('<path class="flow-line" d="M860 94 V120 H100 V96" marker-end="url(#arrow)"/>'
                '<text class="loop-label" x="480" y="143" text-anchor="middle">'
                'Accepted optimizer edits guide the next generation</text></svg>')
    return "".join(body)


def render_html(report):
    check(report)
    esc = html.escape
    search = report["search"]
    settings = search["state"]["plan"]
    aggregate = report["comparison"]["arms"]
    rows = []
    for arm in ARMS:
        result = aggregate[arm]
        cells = [LABELS[arm], count(result), count(result, "business_completed", "business_required"),
                 count(result, "unsafe_episodes"), str(result["duplicate_refunds"]),
                 count(result, "human_interventions"), str(result["provider_calls"])]
        rows.append("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in cells) + "</tr>")
    seed_rows = "".join(
        f'<tr><td>{pair["seed"]}</td><td>{pair["recursive_minus_fixed_optimizer_successes"]:+d}</td>'
        f'<td>{pair["recursive_minus_fixed_optimizer_provider_calls"]:+d}</td></tr>'
        for pair in report["comparison"]["paired_seed_differences"])
    selection_rows = "".join(
        f'<tr><td>{row["seed"]}</td><td>{LABELS[row["arm"]]}</td>'
        f'<td>{row["selected_generation"]}</td><td>{row["accepted_optimizer_changes"]}</td>'
        f'<td>{"Yes" if row["selected_optimizer_changed"] else "No"}</td></tr>'
        for row in search["state"]["runs"])
    budget = search["state"]["runs"][0]["budget"]
    payload = json.dumps({"runs": search["state"]["runs"]}, ensure_ascii=False,
                         allow_nan=False).replace("<", "\\u003c")
    seed_options = "".join(f'<option value="{seed}">{seed}</option>' for seed in settings["seeds"])
    arm_options = "".join(f'<option value="{arm}">{LABELS[arm]}</option>' for arm in ARMS)
    css = (ROOT / "viewer.css").read_text(encoding="utf-8")
    js = (ROOT / "viewer.js").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Bounded recursive improvement · Practical Eval Lab</title><style>{css}</style></head>
<body><a class="skip" href="#main">Skip to evidence</a>
<header><p class="eyebrow">Practical Eval Lab · Recorded experiment</p>
<h1>Can the improvement<br>process improve?</h1>
<p class="intro">Three paired approaches to subscription workflow recovery.
One fixed agent, one fixed optimizer, and one optimizer allowed to evolve.</p>
<p class="tag">Finite configuration search · Synthetic workloads · No model calls</p></header>
<main id="main">
<section class="summary"><h2>What the final evaluation found</h2>
<p class="finding">{esc(assessment(report))}</p>
<div class="stats"><div><strong>{len(settings["seeds"])}</strong><span>paired seeds</span></div>
<div><strong>{settings["generations"]}</strong><span>generations per arm</span></div>
<div><strong>{aggregate["fixed_agent"]["unique_scenario_families"]}</strong><span>final scenario families</span></div></div>
<div class="table-scroll"><table id="results"><caption>Final test · repeated seeds share the same cases</caption>
<thead><tr><th>Arm</th><th>Correct handling</th><th>Business completion</th><th>Unsafe episodes</th>
<th>Duplicate refunds</th><th>Human intervention</th><th>Provider calls</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<p class="small">Correct handling includes clarification and truthful handoff. Permanent outages
remain in the business-completion denominator. All arms use the same fixed authorization guard.
Zero unsafe effects do not establish learned authorization.</p></section>
<section><div class="section-heading"><div><p class="eyebrow">The bounded loop</p>
<h2>Changes must earn their place</h2></div>
<button id="motion" hidden type="button" aria-pressed="false">Pause motion</button></div>
<div id="diagram" class="diagram-scroll">{workflow_svg()}</div>
<p class="small">Moving dashes illustrate flow. They do not encode timing or live execution.
The evaluator, authorization rules and release controls are outside the editable configuration.</p>
<div class="budget"><strong>Same evaluation allowance per arm and seed:</strong>
{budget["development_candidate_evaluations"]} development evaluations × 24 episodes;
{budget["validation_candidate_evaluations"]} validation evaluations × 18 episodes.
Maximum {settings["max_steps_per_episode"]} steps per episode. Actual work varies and is reported.
This is not a matched CPU-time or model-token experiment.</div></section>
<section><h2>Development search</h2>
<p>Mean correct handling across seeds. Final-test feedback never enters this search.</p>
<div class="chart-scroll">{learning_chart(report)}</div>
<p class="legend"><span style="color:#697786">– – Fixed agent</span>
<span style="color:#0D1B2A">— Fixed optimizer</span>
<span style="color:#007B95">— Recursive optimizer</span></p>
<div id="controls" hidden>
<label>Seed <select id="seed">{seed_options}</select></label>
<label>Arm <select id="arm">{arm_options}</select></label>
<button id="previous" type="button">Previous generation</button>
<button id="next" type="button">Next generation</button>
<p id="position" role="status" aria-live="polite"></p></div>
<div id="inspection" hidden><p id="checkpoint"></p>
<div class="code-grid"><div><h3>Workflow configuration</h3><pre id="policy"></pre></div>
<div><h3>Optimizer configuration</h3><pre id="optimizer"></pre></div></div>
<h3>Proposals and decisions</h3><pre id="proposals"></pre></div>
<noscript><p>The tables and development chart remain readable without JavaScript.
Open comparison.json to inspect the complete recorded lineage.</p></noscript>
</section>
<section><h2>Paired final differences</h2>
<p>Recursive optimizer minus fixed optimizer, on the same seed and cases.</p>
<div class="table-scroll"><table><thead><tr><th>Seed</th><th>Change in correct handling</th>
<th>Change in provider calls</th></tr></thead><tbody>{seed_rows}</tbody></table></div>
<h3>Validation-selected revisions</h3>
<div class="table-scroll"><table><thead><tr><th>Seed</th><th>Arm</th><th>Selected generation</th>
<th>Optimizer edits accepted during search</th><th>Selected optimizer changed</th></tr></thead>
<tbody>{selection_rows}</tbody></table></div>
<p class="small">Selection can retain an earlier checkpoint. Accepted edits later in search may
not be in the selected artifact. Review eligibility never deploys a candidate.</p></section>
<section><h2>Scope and evidence</h2><p>{esc(report["notice"])}</p>
<p>The 24 development, 18 validation and 24 final episodes have disjoint authored fault
compositions. They share an author, simulator, fault vocabulary and business rules.
The final cases are public and author-visible. Repeated seeds are correlated.</p>
<p>The default optimizer already considers all failure signals and edits one workflow field.
The recursive arm can also change attribution, ordering and edit width. Results are relative
to these specified strategies.</p>
<details><summary>Content identities and reproduction</summary>
<dl><dt>Report</dt><dd>{report["sha256"]}</dd>
<dt>Protocol</dt><dd>{report["protocol_hash"]}</dd>
<dt>Selected set, committed before final evaluation</dt><dd>{search["selection_commitment"]}</dd>
<dt>Source revision</dt><dd>{esc(str(report["source"]["revision"]))}</dd>
<dt>Working tree contained changes when recorded</dt><dd>{report["source"]["worktree_dirty"]}</dd>
<dt>Recorded UTC</dt><dd>{esc(report["created_at"])}</dd></dl>
<pre>uv run --locked python -m benchmarks.recursive_improvement audit comparison.json</pre>
<p>Audit replays search, selection, selected-policy actions, effects, metrics and review flags.
Hashes identify content; they are not authenticated attestations.</p></details></section>
<footer>Original code and synthetic cases: MIT-0 · Practical Eval Lab<br>
All evidence is local. This viewer makes no external requests.</footer>
</main><script type="application/json" id="evidence">{payload}</script><script>{js}</script></body></html>
"""
