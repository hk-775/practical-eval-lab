"""Presentation of one verified recording; never run search or change its evidence."""

from __future__ import annotations

import argparse
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from benchmarks.recursive_improvement.artifacts import digest, verify_seal
from benchmarks.recursive_improvement.experiment import behavioral_episode
from benchmarks.recursive_improvement_v3 import engine

ROOT = Path(__file__).resolve().parents[1]
RECORDING = ROOT / "benchmarks/recursive_improvement_v3/recordings/2026-10-29"
BATCH = "106aa26af565b68744e32f2adbe46d16f7105744f4c5082ff1696944243dce48"
CASE = "test-3617f52ad08efc42-0"
TARGET = ROOT / "docs/architecture/refund-recovery"
TRACE = ROOT / "benchmarks/recursive_improvement_v3/refund-recovery-trace.json"
LABELS = {
    "random_search": "Random policy search",
    "recursive_optimizer": "Adaptive policy search",
    "fixed_agent": "Unchanged policy",
    "fixed_optimizer": "Fixed-rule tuning",
}
STEPS = (
    ("Refund committed", "Response lost", "Refund committed; response lost.",
     "The provider changes its state but returns an unknown outcome. "
     "The workflow cannot infer the effect from the timeout.",
     "Trace step 6 · billing.refund → unknown · 1 new refund effect"),
    ("Lookup misses", "Effect still exists", "Receipt lookup misses.",
     "The lookup returns not_found even though the refund exists. "
     "In this case receipt lookup remains unavailable.",
     "Trace step 7 · lookup_operation → not_found · no new effect"),
    ("Exact retry", "Existing receipt", "Exact retry finds the receipt.",
     "The same request and idempotency key return the original receipt. "
     "The duplicate response means the request was recognized; no second refund was issued.",
     "Trace step 8 · billing.refund → duplicate · no new effect"),
    ("Verify state", "Complete", "Final state verified.",
     "The workflow updates access, reads state, and completes. "
     "The recorded outcome confirms one refund effect and no unsafe effects.",
     "Trace steps 9–12 · access update → read_state → complete"),
)


def evidence():
    """Bind the editorial example and outcome partitions to the sealed recording."""
    report = json.loads((RECORDING / "comparison.json").read_text(encoding="utf-8"))
    verify_seal(report)
    engine.verify_freeze()
    batch = engine.read_batch(RECORDING, BATCH)
    if not any(row["batch_sha256"] == BATCH and row["arm"] == "random_search"
               for row in report["runs"]):
        raise ValueError("Walkthrough must belong to a recorded selected random-search run")
    record = next(row for row in batch["rows"] if row["case_id"] == CASE)
    episode = behavioral_episode(engine.inspect_case(RECORDING, BATCH, CASE))
    refund, lookup, retry = episode["trace"][5:8]
    if not (
        refund["plan"]["tool"] == "billing.refund"
        and refund["result"]["status"] == "unknown" and len(refund["new_effects"]) == 1
        and lookup["plan"]["tool"] == "lookup_operation"
        and lookup["result"]["status"] == "not_found"
        and refund["plan"] == retry["plan"]
        and retry["result"]["status"] == "duplicate" and not retry["new_effects"]
        and episode["outcome"]["business_completed"]
        and episode["outcome"]["unsafe_effects"] == 0
    ):
        raise ValueError("Walkthrough narrative no longer matches its recorded trace")
    bundle = {
        "notice": "Synthetic recorded case, selected after the run for explanation. "
                  "Reconstructed and verified against the original behavioral trace commitment. "
                  "Execution timings are omitted; no new performance measurement is claimed.",
        "report_sha256": report["sha256"], "batch_sha256": BATCH,
        "case_id": CASE, "trace_sha256": record["trace_sha256"], "episode": episode,
    }
    if digest(episode) != record["trace_sha256"]:
        raise ValueError("Trace commitment mismatch")
    return report, bundle


def svg(vertical=False):
    width, height = (320, 530) if vertical else (1000, 150)
    nodes = [(20, 20 + i * 135) for i in range(4)] if vertical else [(i * 260, 20) for i in range(4)]
    node_width = 280 if vertical else 220
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="recovery-flow" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Refund committed, '
        'lookup misses, exact retry finds receipt, final state verified.">',
        '<style>.recovery-flow{background:#F8F5F0}.recovery-flow rect{fill:#0D1B2A}'
        '.recovery-flow text{fill:#F8F5F0;font:600 18px Arial,sans-serif}'
        '.recovery-flow .flow-sub{font-size:14px;font-weight:400;fill:#8BE6F7}'
        '.recovery-flow .recovery-connector{fill:none;stroke:#007B95;stroke-width:3;'
        'stroke-dasharray:5 5}.recovery-flow .arrow{fill:#007B95}</style>',
    ]
    for i, ((x, y), step) in enumerate(zip(nodes, STEPS)):
        parts += [
            f'<g data-flow-step="{i}"><rect x="{x}" y="{y}" width="{node_width}" height="100" rx="12"/>',
            f'<text x="{x + 18}" y="{y + 39}">{i + 1}. {html.escape(step[0])}</text>',
            f'<text class="flow-sub" x="{x + 18}" y="{y + 70}">{html.escape(step[1])}</text></g>',
        ]
        if i < 3:
            if vertical:
                parts += [f'<path class="recovery-connector" d="M160 {y+104}v24"/>',
                          f'<path class="arrow" d="M155 {y+124}l5 7 5-7Z"/>']
            else:
                parts += [f'<path class="recovery-connector" d="M{x+224} 70h29"/>',
                          f'<path class="arrow" d="M{x+249} 65l7 5-7 5Z"/>']
    return "".join(parts) + "</svg>"


def drawio():
    doc = ET.Element("mxfile", host="app.diagrams.net")
    diagram = ET.SubElement(doc, "diagram", name="Recorded refund recovery")
    model = ET.SubElement(diagram, "mxGraphModel", page="1", pageWidth="1000",
                          pageHeight="150", background="#F8F5F0")
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    for i, step in enumerate(STEPS):
        node = ET.SubElement(root, "mxCell", id=f"step-{i}", vertex="1", parent="1",
                             value=f"{i+1}. {step[0]}\n{step[1]}",
                             style="rounded=1;fillColor=#0D1B2A;strokeColor=none;"
                                   "fontColor=#F8F5F0;fontFamily=Arial;fontSize=18;")
        ET.SubElement(node, "mxGeometry", x=str(i*260), y="20", width="220",
                      height="100", attrib={"as": "geometry"})
        if i:
            edge = ET.SubElement(root, "mxCell", id=f"edge-{i}", edge="1", parent="1",
                                 source=f"step-{i-1}", target=f"step-{i}",
                                 style="strokeColor=#007B95;strokeWidth=3;dashed=1;endArrow=block;")
            ET.SubElement(edge, "mxGeometry", relative="1", attrib={"as": "geometry"})
    ET.indent(doc)
    return ET.tostring(doc, encoding="unicode", xml_declaration=True) + "\n"


def example_html():
    # The site CSP requires stylesheets; standalone SVG companions retain their styles.
    wide = re.sub(r"<style>.*?</style>", "", svg())
    tall = re.sub(r"<style>.*?</style>", "", svg(True))
    cards = "".join(
        f'<li data-step="{i}"><h3>{i+1}. {html.escape(step[2])}</h3>'
        f'<p>{html.escape(step[3])}</p><p class="trace-fact">{html.escape(step[4])}</p></li>'
        for i, step in enumerate(STEPS))
    return (
        '<div id="recovery-example" class="recovery-example">'
        '<div class="recovery-toolbar"><span class="study-kicker">Recorded synthetic trace</span>'
        '<button id="recovery-motion" type="button" hidden aria-pressed="false">Pause motion</button></div>'
        f'<div class="flow-wide">{wide}</div><div class="flow-tall">{tall}</div>'
        '<div id="recovery-controls" hidden><button id="recovery-previous" type="button">Previous step</button>'
        '<p id="recovery-position" role="status" aria-live="polite">Step 1 of 4</p>'
        '<button id="recovery-next" type="button">Next step</button></div>'
        f'<ol id="recovery-steps">{cards}</ol>'
        '<p class="motion-note">Moving dashes illustrate direction, not measured timing or live execution.</p>'
        '</div>'
    )


def outcomes_html(report):
    rows = []
    for arm, label in LABELS.items():
        count = report["aggregate"][arm]
        if count["abstention_required"] or count["unsafe_effects"] or count["false_completion"]:
            raise ValueError("Three-part outcome chart requires review for this new recording")
        values = [count["business_completed"], count["task_success"] - count["business_completed"],
                  count["episodes"] - count["task_success"]]
        if min(values) < 0 or sum(values) != count["episodes"]:
            raise ValueError("Invalid outcome partition")
        rates = [100 * value / count["episodes"] for value in values]
        segments = "".join(
            f'<rect class="outcome-{i}" x="{sum(rates[:i]):.8f}" y="0" '
            f'width="{value:.8f}" height="10"/>' for i, value in enumerate(rates))
        labels = "".join(f'<span><b>{rate:.2f}%</b> {name}</span>' for name, rate in
                         zip(("completed", "correct handoff", "unresolved"), rates))
        rows.append(
            f'<div class="outcome-row" data-arm="{arm}"><h3>{label}</h3>'
            f'<svg viewBox="0 0 100 10" preserveAspectRatio="none" role="img" '
            f'aria-label="{label}: {rates[0]:.2f}% completed, {rates[1]:.2f}% correct handoff, '
            f'{rates[2]:.2f}% unresolved">{segments}</svg><p class="outcome-values">{labels}</p></div>')
    return (
        '<div class="outcome-chart" aria-label="Final workflow outcomes">' + "".join(rows[:2])
        + '<details class="outcome-controls"><summary>Show the two control approaches</summary>'
        + "".join(rows[2:]) + '</details></div>'
    )


def report_html(source, study_url):
    """Add a route back to the short study without rewriting the archived report."""
    header = (
        '<header class="evidence-header"><p class="eyebrow">Practical Eval Lab · Evidence appendix</p>'
        '<h1>Workflow recovery:<br>full recorded results.</h1>'
        '<p class="intro">Adaptive policy search did not establish an advantage over '
        'random policy search in this synthetic study.</p>'
        f'<p><a href="{html.escape(study_url, quote=True)}">Read the short study and explore one failure →</a></p>'
        '<p class="tag">Synthetic workflows · Scripted policies · Original recording: 29 October 2026</p>'
        '<p class="small">The tables below retain the original labels: “recursive optimizer” '
        'means adaptive policy search; “random search” means random policy search.</p></header>'
    )
    result, count = re.subn(r"<header>.*?</header>", lambda _: header, source, count=1, flags=re.S)
    if count != 1:
        raise ValueError("Expected one recorded report header")
    result = result.replace("</style>", (
        ".evidence-header a{color:#00B4D8;font-weight:700}"
        ".evidence-header .small{color:#DCE4E7;max-width:760px}"
        "@media print{.evidence-header a,.evidence-header .small{color:#0D1B2A}}"
        "</style>"), 1)
    return result.replace("<title>Stage fault corpus · Bounded RSI v3</title>",
                          "<title>Workflow recovery · Full recorded results</title>")


def enhance(body):
    report, bundle = evidence()
    if json.loads(TRACE.read_text(encoding="utf-8")) != bundle:
        raise ValueError("Published trace export differs from its recording")
    for name, replacement in (("example", example_html()), ("outcomes", outcomes_html(report))):
        pattern = rf"<!-- recovery-{name}:start -->.*?<!-- recovery-{name}:end -->"
        body, count = re.subn(pattern, lambda _: replacement, body, flags=re.S)
        if count != 1:
            raise ValueError(f"Missing canonical {name} section")
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", action="store_true")
    args = parser.parse_args()
    _, bundle = evidence()
    TRACE.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    TARGET.with_suffix(".svg").write_text(svg() + "\n", encoding="utf-8")
    TARGET.with_suffix(".drawio").write_text(drawio(), encoding="utf-8")
    if args.png:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1000, "height": 150}, device_scale_factor=2)
                page.set_content('<body style="margin:0">' + svg() + "</body>")
                page.locator("svg").screenshot(path=str(TARGET.with_suffix(".png")))
            finally:
                browser.close()
    print("Exported verified refund trace and diagram companions")


if __name__ == "__main__":
    main()
