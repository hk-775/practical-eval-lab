"""Offline report with actual trace playback and illustrative connector motion."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from .contract import ROOT

LABELS = {
    "unrestricted": "Unrestricted",
    "permissions": "Permissions",
    "invariants": "Business invariants",
    "deny_all": "Deny all",
}


def count(value):
    return f'{value["numerator"]}/{value["denominator"]}'


def render_markdown(report):
    rows = [
        "# Subscription workflow: recorded synthetic results",
        "",
        report["notice"],
        "",
        f'Partition: **{report["split"]}**. Recorded: `{report["created_at"]}`.',
        "",
        "| Control | Correct handling | Legitimate completion | Unsafe episodes | Duplicate refunds | Human intervention | p95 simulator ms |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, config in report["configurations"].items():
        m = config["metrics"]
        rows.append(
            f"| {LABELS[name]} | {count(m['task_success'])} | {count(m['legitimate_completion'])} "
            f"| {count(m['unsafe_episode_rate'])} | {m['duplicate_refund_effects']} "
            f"| {count(m['human_intervention'])} | {m['p95_simulator_ms']:.3f} |"
        )
    rows += [
        "",
        "Correct handling includes required clarification and truthful handoff. Legitimate",
        "completion counts only fulfilled changes, including unavailable-provider cases in",
        "its denominator. Blocking everything cannot earn legitimate completion.",
        "Human intervention includes both clarification and handoff; human wait is not timed.",
        "",
        "## Condition-level task handling",
        "",
        "| Condition | " + " | ".join(LABELS[name] for name in report["configurations"]) + " |",
        "|---|" + "---:|" * len(report["configurations"]),
    ]
    first = next(iter(report["configurations"].values()))
    for condition in first["conditions"]:
        rows.append("| " + condition + " | " + " | ".join(
            count(config["conditions"][condition]["task_success"])
            for config in report["configurations"].values()) + " |")
    rows += [
        "",
        "## Evidence identity",
        "",
        f'- Report SHA-256: `{report["report_hash"]}`',
        f'- Protocol SHA-256: `{report["protocol_hash"]}`',
        f'- Dataset SHA-256: `{report["dataset_sha256"]}`',
        f'- Source revision: `{report["source_revision"]}`; dirty worktree: `{report["worktree_dirty"]}`.',
        "",
        "The content hashes identify the evaluated implementation even when its source",
        "revision precedes an uncommitted change. Replay verifies effects and metrics;",
        "hashes are not independent attestations.",
        "",
        "These public cases share scenario templates. Counts describe this regression",
        "suite, not production risk or model generalization. See the protocol for scope,",
        "case construction, grading, adapter boundaries, and operational limitations.",
        "",
    ]
    return "\n".join(rows)


def render_html(report):
    escape = html.escape
    recorded = datetime.fromisoformat(report["created_at"]).astimezone(timezone.utc).strftime(
        "%d %b %Y, %H:%M UTC")
    rows = []
    for name, config in report["configurations"].items():
        m = config["metrics"]
        values = (LABELS[name], count(m["task_success"]), count(m["legitimate_completion"]),
                  count(m["unsafe_episode_rate"]), str(m["duplicate_refund_effects"]),
                  count(m["human_intervention"]), f'{m["p95_simulator_ms"]:.3f}')
        rows.append("<tr>" + "".join(f"<td>{escape(value)}</td>" for value in values) + "</tr>")
    fallback = []
    for name, config in report["configurations"].items():
        episode = next(e for e in config["episodes"] if e["condition"] == "early_access_revocation")
        target = next(iter(episode["outcome"]["final_records"].values()))
        cancel_day = target["cancel_at_day"] if target["cancel_at_day"] is not None else "not scheduled"
        fallback.append(
            f'<li><strong>{escape(LABELS[name])}</strong>: cancellation day '
            f'{cancel_day}; access ends day {target["access_until_day"]}; '
            f'unsafe effects {episode["outcome"]["unsafe_effects"]}.</li>'
        )
    payload = json.dumps(report, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    css = (ROOT / "viewer.css").read_text(encoding="utf-8")
    js = (ROOT / "viewer.js").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>Subscription state evaluation · Practical Eval Lab</title><style>{css}</style></head>
<body><a class="skip" href="#main">Skip to results</a>
<header><p class="eyebrow">Practical Eval Lab · Synthetic engineering evaluation</p>
<h1>Preserving business state<br>across agent actions.</h1>
<p class="lead">A successful tool call does not establish that billing and access agree with the customer’s confirmed request.</p>
<p>Recorded {escape(recorded)} · {escape(report["split"])} partition</p></header>
<main id="main"><section aria-labelledby="results"><h2 id="results">Executed results</h2>
<p>{escape(report["notice"])}</p>
<p class="scroll-hint">Scroll the table horizontally to inspect every metric.</p>
<div class="table-scroll" tabindex="0" role="region" aria-label="Comparison results">
<table><thead><tr><th>Control</th><th>Correct handling</th><th>Legitimate completion</th>
<th>Unsafe episodes</th><th>Duplicate refunds</th><th>Human intervention</th><th>p95 simulator ms</th>
</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p>Correct handling includes clarification and handoff. Legitimate completion requires the requested
business change; unavailable-provider cases remain in its denominator. Human wait is not timed.</p></section>
<section aria-labelledby="workflow"><h2 id="workflow">Inspect the workflow</h2>
<p>The moving dashes illustrate flow. They do not represent execution timing or a live agent.</p>
<button id="motion" hidden type="button" aria-pressed="false">Pause motion</button>
<p id="motion-status" class="small">Static view. Optional script enables illustrative motion and trace controls.</p>
<p class="scroll-hint">Scroll the diagram horizontally to follow all five stages.</p>
<div class="diagram-scroll" tabindex="0" role="region" aria-label="Subscription workflow diagram">
<svg viewBox="0 0 1000 145" role="img" aria-labelledby="flow-title flow-desc">
<title id="flow-title">Confirmed intent to verified billing and access state</title>
<desc id="flow-desc">Trusted intent passes through the mutation guard to billing and access. The evaluator checks observed effects and final state.</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#0D1B2A"/></marker></defs>
<g class="connectors" fill="none" stroke="#0D1B2A" stroke-width="3" marker-end="url(#arrow)">
<path class="flow-line" d="M170 64H218"/><path class="flow-line" d="M370 64H418"/>
<path class="flow-line" d="M570 64H618"/><path class="flow-line" d="M770 64H818"/></g>
<g class="nodes" text-anchor="middle" font-family="system-ui" font-size="17">
<rect x="10" y="25" width="160" height="78" rx="10"/><text x="90" y="59">Confirmed intent</text><text x="90" y="83" class="sub">Scope + effective day</text>
<rect x="220" y="25" width="150" height="78" rx="10"/><text x="295" y="59">Mutation guard</text><text x="295" y="83" class="sub">Current authority</text>
<rect x="420" y="25" width="150" height="78" rx="10"/><text x="495" y="59">Billing</text><text x="495" y="83" class="sub">Cancel + refund</text>
<rect x="620" y="25" width="150" height="78" rx="10"/><text x="695" y="59">Access</text><text x="695" y="83" class="sub">Agreed expiry</text>
<rect x="820" y="25" width="170" height="78" rx="10"/><text x="905" y="59">Verify state</text><text x="905" y="83" class="sub">Effects + outcome</text></g></svg></div>
<div id="controls" hidden><div class="controls">
<label>Control profile<select id="profile"></select></label>
<label>Scenario<select id="episode"></select></label></div>
<h3 id="episode-title">Recorded episode</h3><p id="outcome"></p>
<div class="controls"><button id="previous" type="button">Previous step</button>
<button id="next" type="button">Next step</button><span id="position" aria-live="polite"></span></div>
<div class="trace-columns"><div><h3>Proposed action</h3><pre id="proposal"></pre></div>
<div><h3>Tool feedback</h3><pre id="feedback"></pre></div></div>
<h3>Committed effects at this step</h3><pre id="effects"></pre>
<details><summary>Final state and grading</summary><pre id="final"></pre></details></div>
<h3>Example: cancellation at renewal with an early-access proposal</h3>
<ul>{"".join(fallback)}</ul>
<noscript><p>The comparison and example above remain available without JavaScript. Open the recorded JSON to inspect every step.</p></noscript></section>
<section><h2>Evidence and limits</h2><p>Every command, result, committed effect, and final state is recorded.
The independent grader retains unsafe effects even when later repaired. Replay checks the event chain and recalculates metrics.</p>
<p>The simulator serializes writes in memory. Public parameterized cases share templates.
There is no production provider integration, durability claim, or statistical estimate of enterprise risk.</p>
<dl><dt>Report SHA-256</dt><dd><code>{report["report_hash"]}</code></dd>
<dt>Protocol SHA-256</dt><dd><code>{report["protocol_hash"]}</code></dd></dl></section>
<footer>Original code and synthetic examples: MIT-0. No customer or proprietary data.</footer></main>
<script id="report" type="application/json">{payload}</script><script>{js}</script></body></html>
"""
