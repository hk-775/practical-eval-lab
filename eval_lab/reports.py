"""Portable reports: structural validation, local history, and escaped static HTML."""

from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path
from uuid import uuid4

from .core import aggregate_metrics, compare_reports, data_notice, digest, gate_settings, threshold_value, validate_cases, valid_usage
from .suites import settings_for

MAX_REPORT_BYTES = 20_000_000


def validate_report(payload):
    try:
        if len(json.dumps(payload, allow_nan=False).encode()) > MAX_REPORT_BYTES:
            raise ValueError("Report exceeds 20 MB")
        if not isinstance(payload, dict):
            raise ValueError("Report must be an object")
        if "before" in payload or "after" in payload:
            before, after = validate_report(payload["before"]), validate_report(payload["after"])
            if "results" not in before or "results" not in after:
                raise ValueError("Nested comparisons are not supported")
            return compare_reports(before, after)
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 2:
            raise ValueError("Import requires a version 2 report; rerun older reports")
        if payload["split"] not in ("dev", "holdout"):
            raise ValueError("Invalid report split")
        if any(not isinstance(payload[k], str) or not re.fullmatch(r"[0-9a-f]{64}", payload[k]) for k in ("dataset_hash", "grader_hash")):
            raise ValueError("Invalid report fingerprints")
        threshold_value(payload["score"])
        threshold_value(payload["threshold"])
        settings_for(payload["suite"], payload["settings"])
        policy = gate_settings(payload["gate_policy"])
        candidate = payload["candidate"]
        if not isinstance(candidate, dict) or any(not isinstance(candidate[k], str) or not candidate[k] for k in ("name", "kind")):
            raise ValueError("Invalid candidate identity")
        if not isinstance(payload["created_at"], str):
            raise ValueError("Invalid report timestamp")
        results = payload["results"]
        if not isinstance(results, list) or not 1 <= len(results) <= 5000:
            raise ValueError("Report must contain 1–5,000 results")
        trials, count = payload["trials"], payload["case_count"]
        if type(trials) is not int or not 1 <= trials <= 20 or type(count) is not int or not 1 <= count <= 500:
            raise ValueError("Invalid trial or case count")
        seen, case_trials, references = set(), {}, {}
        for r in results:
            if not isinstance(r["id"], str) or r["id"] in seen:
                raise ValueError("Result IDs must be unique")
            seen.add(r["id"])
            checks = r["checks"]
            if not isinstance(checks, list) or not checks or any(
                not isinstance(c, dict) or not isinstance(c["name"], str) or type(c["passed"]) is not bool or not isinstance(c["detail"], str) for c in checks
            ):
                raise ValueError("Invalid grader checks")
            if type(r["passed"]) is not bool or r["passed"] != all(c["passed"] for c in checks):
                raise ValueError("Result verdict does not agree with checks")
            if type(r["trial"]) is not int or not 1 <= r["trial"] <= trials:
                raise ValueError("Invalid trial index")
            key = r["case_id"]
            base = {k: r[k] for k in ("input", "expected", "tags")}
            base["id"] = key
            if key in references and references[key] != base:
                raise ValueError("Trials must use identical cases")
            references[key] = base
            trial_set = case_trials.setdefault(key, set())
            if r["trial"] in trial_set:
                raise ValueError("Duplicate trial for a case")
            trial_set.add(r["trial"])
            if "actual" not in r or r["error"] is not None and not isinstance(r["error"], str):
                raise ValueError("Invalid result output/error")
            valid_usage(r["usage"])
            for field in ("candidate_latency_ms", "grader_latency_ms", "latency_ms"):
                number = r[field]
                if type(number) not in (int, float) or not math.isfinite(number) or number < 0:
                    raise ValueError("Invalid latency measurement")
            if not isinstance(r.get("metrics", {}), dict) or any(
                type(n) not in (int, float) or not math.isfinite(n) for n in r.get("metrics", {}).values()
            ):
                raise ValueError("Invalid case measurements")
        validate_cases(payload["suite"], list(references.values()))
        if digest(list(references.values())) != payload["dataset_hash"]:
            raise ValueError("Dataset fingerprint does not match report cases")
        if len(references) != count or any(len(ts) != trials for ts in case_trials.values()):
            raise ValueError("Incomplete trials")
        passed = sum(r["passed"] for r in results)
        if (type(payload["total"]) is not int or payload["total"] != len(results)
                or payload["passed"] != passed or payload["failed"] != len(results) - passed
                or payload["score"] != passed / len(results)):
            raise ValueError("Report totals do not agree with its results")
        if type(payload["passed_gate"]) is not bool or not isinstance(payload["gates"], list) or not payload["gates"]:
            raise ValueError("Invalid report gates")
        for gate in payload["gates"]:
            if type(gate["passed"]) is not bool or not isinstance(gate["name"], str) or not isinstance(gate["detail"], str):
                raise ValueError("Invalid report gate")
        if not isinstance(payload["slices"], dict) or not isinstance(payload["metrics"], dict):
            raise ValueError("Invalid report measurements")
        for tag, bucket in payload["slices"].items():
            if not isinstance(tag, str) or type(bucket["total"]) is not int or bucket["total"] < 1:
                raise ValueError("Invalid report slice")
            threshold_value(bucket["accuracy"])
            if type(bucket["passed"]) is not int or not 0 <= bucket["passed"] <= bucket["total"]:
                raise ValueError("Invalid report slice counts")
        tags = {t for r in results for t in r["tags"]}
        slices = {}
        for tag in tags:
            members = [r for r in results if tag in r["tags"]]
            score = sum(r["passed"] for r in members)
            slices[tag] = {"passed": score, "total": len(members), "accuracy": score / len(members)}
        if slices != payload["slices"]:
            raise ValueError("Slice totals do not match report cases")
        if (set(policy["critical_tags"]) | set(policy["min_slices"])) - tags:
            raise ValueError("Gate tags must exist in the dataset")
        expected_gates = {"overall": payload["score"] >= payload["threshold"]}
        expected_gates.update({f"critical:{tag}": slices[tag]["accuracy"] == 1 for tag in policy["critical_tags"]})
        expected_gates.update({f"slice:{tag}": slices[tag]["accuracy"] >= n for tag, n in policy["min_slices"].items()})
        if {g["name"]: g["passed"] for g in payload["gates"]} != expected_gates or payload["passed_gate"] != all(expected_gates.values()):
            raise ValueError("Gate verdicts do not match report results")
        errors = sum(r["error"] is not None for r in results)
        if type(payload["execution_errors"]) is not int or payload["execution_errors"] != errors:
            raise ValueError("Execution error count does not match results")
        # Recompute derived measurements before rendering untrusted imports.
        return {**payload, "metrics": aggregate_metrics(payload["suite"], results, trials),
                "data_notice": data_notice(payload["suite"])}
    except (KeyError, TypeError, RecursionError) as exc:
        raise ValueError("Malformed report; export a complete version 2 report") from exc


def html_report(payload):
    payload = validate_report(payload)
    report = payload.get("after", payload)
    esc = lambda value: html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
    compare = "before" in payload
    heading = f"{report['suite']} · {report['candidate']['name']}"
    if compare:
        heading = f"{report['suite']} · {payload['before']['candidate']['name']} → {report['candidate']['name']}"
    rows = []
    changes = {c["id"]: c for c in payload.get("changes", [])}
    for r in report["results"]:
        check_text = "\n".join(f"{'PASS' if c['passed'] else 'FAIL'} {c['name']}: {c['detail']}" for c in r["checks"])
        old = f"<h4>Before</h4><pre>{esc(changes[r['id']]['before']['actual'])}</pre>" if compare else ""
        rows.append(f"""<article class="case"><h3>{esc(r['id'])} · {'PASS' if r['passed'] else 'FAIL'}</h3>
<p>{esc(', '.join(r['tags']))}</p><details><summary>Input and reference</summary><pre>{esc(r['input'])}</pre><h4>Reference</h4><pre>{esc(r['expected'])}</pre></details>
{old}<h4>Output</h4><pre>{esc(r['actual'])}</pre><details><summary>Grader checks</summary><pre>{esc(check_text)}</pre></details></article>""")
    gates = payload.get("gates", report["gates"])
    gate_text = "; ".join(f"{g['name']}: {'PASS' if g['passed'] else 'FAIL'}" for g in gates)
    delta = f" · change {payload['delta']:+.1%} · {payload['regressed']} regressions" if compare else ""
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'">
<title>{esc(heading)} — Practical Eval Lab</title><style>
body{{font:16px/1.6 system-ui,sans-serif;color:#14233f;background:#fff;margin:0 auto;padding:32px;max-width:1000px}}
h1,h2,h3{{line-height:1.2}}h1{{color:#075be8}}.case{{border:1px solid #ccd4e0;padding:20px;margin:20px 0;border-radius:12px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6fa;padding:16px}}summary{{cursor:pointer;color:#075be8}}
.score{{font-size:24px;font-weight:700}}code{{overflow-wrap:anywhere}}</style>
<header><p>Practical Eval Lab · saved experiment</p><h1>{esc(heading)}</h1>
<p class="score">{report['passed']}/{report['total']} passed ({report['score']:.1%}){esc(delta)}</p>
<p>{esc(report['split'])} · {esc(report['created_at'])} · {report['trials']} trial(s)</p><p>{esc(gate_text)}</p></header>
<p>Teaching data; results describe these cases only. Candidate kind: {esc(report['candidate']['kind'])}.
Imported reports are user-supplied evidence, not authenticated measurements. Review inputs and outputs before sharing.</p>
<details><summary>Measurements and reproducibility</summary><pre>{esc(report['metrics'])}</pre>
<p>Dataset <code>{esc(report['dataset_hash'])}</code><br>Grader <code>{esc(report['grader_hash'])}</code></p>
<pre>{esc(report['candidate'])}</pre></details><h2>Case results</h2>{''.join(rows)}
<details><summary>Data attribution and license</summary><pre>{esc(report['data_notice'])}</pre></details>
<footer>Standalone report · no scripts, external assets, or model calls</footer></html>"""


class ReportStore:
    def __init__(self, root):
        self.root = Path(root) / "runs"

    def save(self, report, *, imported=False):
        report = validate_report(report)
        key = uuid4().hex
        record = {"id": key, "imported": imported, "report": report}
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{key}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        temporary.replace(path)
        return key

    def load(self, key):
        if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{32}", key):
            raise ValueError("Invalid run ID")
        record = json.loads((self.root / f"{key}.json").read_text(encoding="utf-8"))
        record["report"] = validate_report(record["report"])
        return record

    def list(self):
        records = []
        paths = sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:200]
        for path in paths:
            try:
                record = self.load(path.stem)
                report = record["report"]
                after = report.get("after", report)
                label = after["candidate"]["name"]
                if "before" in report:
                    label = report["before"]["candidate"]["name"] + " → " + label
                records.append({"id": record["id"], "imported": record["imported"], "suite": after["suite"],
                                "split": after["split"], "created_at": after["created_at"], "candidate": label,
                                "score": after["score"]})
            except (ValueError, OSError):
                continue
        return records
