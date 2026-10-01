"""Render the sourced incident catalog into repository docs and an offline webpage."""

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def render():
    catalog = json.loads((ROOT / "examples/incidents/case_studies.json").read_text(encoding="utf-8"))
    intro = ("These are publicly documented incidents, not claims that the underlying systems used this lab. "
             "Documented events are separated from retrospective evaluation proposals. Such tests could expose "
             "the illustrated failure modes; the public record usually cannot prove they would have prevented "
             "the incident. Evals also need enforceable deployment gates, runtime controls, and accountable review.")
    markdown = ["# Public incidents: what would you evaluate?\n", intro,
                f"\nSources reviewed {catalog['reviewed_on']}. Summaries are paraphrased; original sources remain linked.",
                "\n| Public case | Failure mode | Related example |\n|---|---|---|"]
    esc = html.escape
    cards, navigation = [], []
    for study in catalog["studies"]:
        source = study["source"]
        markdown.append(f"| [{study['title']}](#{study['id']}) | {study['failure']} | `{study['suite']}` |")
        navigation.append(f'<li><a href="#{esc(study["id"])}">{esc(study["title"])}</a></li>')
        source_md = f"[{source['publisher']}: {source['title']}]({source['url']})"
        source_html = f'<a href="{esc(source["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{esc(source["publisher"])}: {esc(source["title"])}</a>'
        if source.get("additional_url"):
            source_md += f" · [Official case record]({source['additional_url']})"
            source_html += f' · <a href="{esc(source["additional_url"], quote=True)}" target="_blank" rel="noopener noreferrer">Official case record</a>'
        fields = [("Documented event", study["documented"]),
                  ("Failure mode", study["failure"]),
                  ("Proposed release gate", study["gate"]),
                  ("Exercise", study["exercise"]),
                  ("Coverage in this lab", study["coverage"]),
                  ("Limits of the prevention claim", study["limit"])]
        body = "".join(f"<h3>{esc(label)}</h3><p>{esc(value)}</p>" for label, value in fields[:2])
        body += "<h3>Proposed evals · retrospective design</h3><ol>" + "".join(f"<li>{esc(e)}</li>" for e in study["evals"]) + "</ol>"
        body += "".join(f"<h3>{esc(label)}</h3><p>{esc(value)}</p>" for label, value in fields[2:])
        cards.append(f"""<article id="{esc(study['id'])}" class="panel incident-card">
<p class="eyebrow">{esc(study['event'])}</p><h2>{esc(study['title'])}</h2>{body}
<p class="notice">Source: {source_html}<br>{esc(source['locator'])}</p>
<p class="muted small">{esc(source['access'])}</p>
<a class="outline-button" href="./?suite={esc(study['suite'])}">Open related eval →</a></article>""")
    for study in catalog["studies"]:
        source = study["source"]
        markdown.extend([f'\n<a id="{study["id"]}"></a>\n\n## {study["title"]}\n', f"**When:** {study['event']}\n",
                         f"**Documented event.** {study['documented']}\n",
                         f"**Source:** [{source['publisher']} — {source['title']}]({source['url']}); {source['locator']}. {source['access']}\n"])
        if source.get("additional_url"):
            markdown.append(f"[Official case record]({source['additional_url']}).\n")
        markdown.extend([f"**Failure mode.** {study['failure']}\n", "**Proposed evals (retrospective):**\n"])
        markdown.extend(f"{i}. {value}" for i, value in enumerate(study["evals"], 1))
        markdown.extend([f"\n**Proposed release gate.** {study['gate']}\n",
                         f"**Exercise.** {study['exercise']}\n",
                         f"**Implemented coverage.** {study['coverage']}\n",
                         f"**Prevention claim limits.** {study['limit']}\n"])
    exercise = """
## Run a fictional analogue

The [incident-inspired RAG profile](../examples/incidents/rag-profile.json) has four
invented cases: a policy conflict, an unreliable source, missing authority, and an
untrusted instruction. It contains no actual customer conversation, real airline
policy, legal advice, or reproduction of the affected proprietary systems.

```bash
uv run --locked eval-lab compare --suite rag \\
  --config examples/incidents/rag-profile.json --critical-tag critical \\
  --report reports/incident-inspired.json --html reports/incident-inspired.html
```

In the webpage, select RAG and import that profile. The default local baseline
uses misleading text; the changed candidate respects the fixture's explicit
trust/current flags. Passing this toy exercise does not establish source-trust
inference, real-world safety, or prevention of any named incident.

For a new incident, preserve this chain: observed failure → relevant test population
→ independently reviewed success criteria → grader → severity/slice gate →
deployment action. Include positive controls and benign near-misses so the system
cannot pass merely by refusing everything. Keep a separate fresh sample for final
assessment and production monitoring.
"""
    markdown.append(exercise)
    webpage = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Six documented AI incidents and the evals that could expose their failure modes.">
<title>Why evals matter · Practical Eval Lab</title>
<link rel="stylesheet" href="./styles.css"><link rel="icon" href="./favicon.svg" type="image/svg+xml"></head>
<body><header class="case-study-hero"><nav class="nav"><a class="brand" href="./"><span class="brand-mark" aria-hidden="true">E</span>Practical Eval Lab</a><a class="text-button" href="./">Back to the lab →</a></nav>
<div class="hero-copy"><p class="eyebrow">Learn from public incidents</p><h1>Failures make<br><span>better tests.</span></h1>
<p class="hero-description">Six public cases. Specific failure modes. Tests you can reason about.</p></div></header>
<main class="page-shell case-study-page"><section class="panel incident-card"><h2>Evidence before hindsight</h2>
<p>{esc(intro)}</p><p class="muted">Sources reviewed {esc(catalog['reviewed_on'])}. Source links open externally; this page itself works offline.</p><ul>{''.join(navigation)}</ul></section>
{''.join(cards)}
<footer><p>Start with a failure you can explain. Decide what must block a release.</p><p><a href="./">Return to the six runnable examples →</a></p></footer></main></body></html>"""
    return {"docs/incident-case-studies.md": "\n".join(markdown).rstrip() + "\n",
            "eval_lab/web/incidents.html": webpage + "\n"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for filename, content in render().items():
        path = ROOT / filename
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Regenerate {filename} with python -m scripts.render_incidents")
        else:
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
