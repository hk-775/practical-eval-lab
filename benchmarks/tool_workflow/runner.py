"""Calibration on reference states; final scoring on executed candidate rollouts."""

from __future__ import annotations

import copy
import platform
import time
from datetime import datetime, timezone

from benchmarks.decision_models.contract import ROOT as MODEL_ROOT
from .candidates import create, rule_plan
from .data import ROOT, digest, load
from .metrics import interval, summarize
from .simulator import (
    execute, judge_plan, new_session, observation, outcome, reference_observations,
)

GRID = (.0, .5, .6, .7, .8, .9, .95, .99, 1.)
PROTOCOL = "executed-support-workflow-v2"


def protocol_hash():
    paths = sorted(ROOT.glob("*.py")) + [ROOT / "PROTOCOL.md"]
    paths += [MODEL_ROOT / p for p in ("adapters.py", "local_models.py", "contract.py", "models.json", "runtime/uv.lock")]
    return digest([(str(p.relative_to(ROOT.parent)), p.read_text(encoding="utf-8")) for p in paths])


def seal(report):
    report["report_hash"] = digest({k: v for k, v in report.items() if k != "report_hash"})
    return report


def verify(report, kind):
    if report.get("kind") != kind or report.get("report_hash") != digest({k: v for k, v in report.items() if k != "report_hash"}):
        raise ValueError("Wrong or modified workflow report")
    return report


def make_runtime(name, device):
    started = time.perf_counter()
    fn, info, synchronize = create(name, device)
    setup_ms = (time.perf_counter() - started) * 1000
    probe = {
        "authorization": {"can_update": True},
        "tickets": [{"id": "SYN-8000", "priority": "low", "locked": False},
                    {"id": "SYN-8001", "priority": "normal", "locked": False}],
        "messages": ["Please read ticket SYN-8000 without changing it."],
        "last_tool_result": None,
    }
    warmup = []
    for _ in range(3):
        synchronize()
        start = time.perf_counter()
        fn(copy.deepcopy(probe))
        synchronize()
        warmup.append((time.perf_counter() - start) * 1000)
    return fn, info, synchronize, setup_ms, warmup


def base_report(kind, info, split, manifest, setup_ms, warmup):
    return {
        "kind": kind, "schema_version": 1, "protocol": PROTOCOL,
        "protocol_hash": protocol_hash(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate": info, "candidate_hash": digest(info),
        "dataset_version": manifest["version"], "split": split,
        "dataset_sha256": manifest["files"][split]["sha256"],
        "development_sha256": manifest["files"]["development"]["sha256"],
        "hardware": {"system": platform.system(), "machine": platform.machine()},
        "python": platform.python_version(),
        "setup_ms_including_download_if_needed": setup_ms,
        "warmup_ms": warmup, "warmup_excluded": True,
        "cost_usd": None,
        "notice": "Synthetic in-memory support workflow. Scripted user replies have no human wait. No external service, Jev, or general-model fallback is executed. Costs unknown. Timing is simulator wall time, not an enterprise service SLO.",
    }


def calibration(name, device="cpu", runtime=None):
    cases, manifest = load("calibration")
    fn, info, synchronize, setup, warmup = runtime or make_runtime(name, device)
    rows = []
    for case in cases:
        session = new_session(case)
        for obs, reference in reference_observations(case):
            synchronize()
            started = time.perf_counter()
            error, proposal = None, None
            try:
                proposal = fn(copy.deepcopy(obs))
                synchronize()
            except Exception as exc:
                synchronize()
                error = type(exc).__name__
            elapsed = (time.perf_counter() - started) * 1000
            judgment = judge_plan(session, proposal or {"action": "invalid", "arguments": {}})
            rows.append({
                "case_id": case["id"], "family": case["family"], "condition": case["condition"],
                "observation_hash": digest(obs), "reference": reference,
                "proposal": proposal, "correct": judgment["correct"],
                "confidence": proposal["confidence"] if proposal else None,
                "error": error, "latency_ms": elapsed,
            })
            execute(session, reference)
    report = base_report("workflow-calibration", info, "calibration", manifest, setup, warmup)
    report.update({"states": rows, "errors": sum(r["error"] is not None for r in rows),
                   "episodes": len(cases), "families": len({c["family"] for c in cases})})
    return seal(report)


def fit_gate(report, max_error=.05, min_families=20):
    verify(report, "workflow-calibration")
    if report["errors"]:
        raise ValueError("Resolve execution errors before calibration")
    if not 0 <= max_error <= 1 or type(min_families) is not int or min_families < 1:
        raise ValueError("Invalid gate criterion")
    rows = report["states"]
    grid = []
    for threshold in GRID:
        accepted = [r for r in rows if r["confidence"] >= threshold]
        errors = sum(not r["correct"] for r in accepted)
        families = len({r["family"] for r in accepted})
        risk = errors / len(accepted) if accepted else None
        grid.append({
            "threshold": threshold, "accepted_states": len(accepted),
            "accepted_families": families, "errors": errors, "empirical_error": risk,
            "qualifies": bool(accepted and families >= min_families and risk <= max_error),
        })
    eligible = [r for r in grid if r["qualifies"]]
    selected = min(eligible, key=lambda r: (-r["accepted_states"], r["threshold"])) if eligible else None
    return seal({
        "kind": "workflow-gate", "protocol_hash": report["protocol_hash"],
        "candidate_hash": report["candidate_hash"], "source_report_hash": report["report_hash"],
        "calibration_sha256": report["dataset_sha256"],
        "development_sha256": report["development_sha256"],
        "families": sorted({r["family"] for r in rows}),
        "threshold": selected["threshold"] if selected else None,
        "statistic": "minimum selected-option probability across action and required arguments",
        "max_empirical_error": max_error, "min_accepted_families": min_families,
        "grid": grid,
        "notice": "Development-frozen grid fitted to calibration reference states. The error criterion is empirical, not a population bound. Final test executes candidate-selected trajectories. A null gate bypasses the primary and runs the rules fallback.",
    })


def run_episode(case, fn, synchronize, strategy, threshold):
    session = new_session(case)
    traces = []
    episode_start = time.perf_counter()
    for index in range(3):
        obs = observation(session)
        bypassed = strategy == "gated_rules" and threshold is None
        proposal, error, primary_ms = None, None, 0.
        if not bypassed:
            synchronize()
            started = time.perf_counter()
            try:
                proposal = fn(copy.deepcopy(obs))
                synchronize()
            except Exception as exc:
                synchronize()
                error = type(exc).__name__
            primary_ms = (time.perf_counter() - started) * 1000
        fallback_used = strategy == "gated_rules" and (
            bypassed or error is not None or proposal["confidence"] < threshold
        )
        fallback_ms = 0.
        if fallback_used:
            started = time.perf_counter()
            selected = rule_plan(copy.deepcopy(obs))
            fallback_ms = (time.perf_counter() - started) * 1000
        else:
            selected = proposal or {"action": "invalid", "arguments": {}}
        judgment = judge_plan(session, selected)
        proposal_judgment = judge_plan(session, proposal) if proposal else None
        started = time.perf_counter()
        result = execute(session, selected)
        tool_ms = (time.perf_counter() - started) * 1000
        traces.append({
            "step": index + 1, "observation_hash": digest(obs),
            "proposal": proposal, "proposal_judgment": proposal_judgment,
            "primary_error": error, "primary_bypassed": bypassed,
            "primary_ms": primary_ms, "fallback_used": fallback_used, "fallback_ms": fallback_ms,
            "selected": selected, "judgment": judgment, "execution": result, "tool_ms": tool_ms,
        })
        if session["terminal"]:
            break
    elapsed = (time.perf_counter() - episode_start) * 1000
    return {
        "case_id": case["id"], "family": case["family"], "stratum": case["stratum"],
        "condition": case["condition"], "clarification_required": bool(case["goal"]["clarification"]),
        "latency_ms": elapsed, "outcome": outcome(session, traces), "trace": traces,
    }


def evaluate(name, split="test", device="cpu", strategy="direct", gate=None, runtime=None):
    if strategy not in ("direct", "gated_rules") or split not in ("development", "test"):
        raise ValueError("Invalid evaluation configuration")
    if strategy == "direct" and gate is not None:
        raise ValueError("A direct run does not use a gate")
    cases, manifest = load(split)
    fn, info, synchronize, setup, warmup = runtime or make_runtime(name, device)
    threshold = None
    if strategy == "gated_rules":
        if split != "test" or gate is None:
            raise ValueError("The gated cascade needs calibration evidence and a final test split")
        verify(gate, "workflow-gate")
        if (gate["candidate_hash"] != digest(info) or gate["protocol_hash"] != protocol_hash()
                or gate["calibration_sha256"] != manifest["files"]["calibration"]["sha256"]
                or gate["development_sha256"] != manifest["files"]["development"]["sha256"]
                or set(gate["families"]) & {c["family"] for c in cases}):
            raise ValueError("Gate identity or partition differs")
        threshold = gate["threshold"]
    episodes = [run_episode(case, fn, synchronize, strategy, threshold) for case in cases]
    report = base_report("workflow-evaluation", info, split, manifest, setup, warmup)
    report.update({
        "strategy": strategy, "gate_hash": gate["report_hash"] if gate else None,
        "threshold": threshold, "max_steps": 3,
        "metrics": summarize(episodes),
        "uncertainty": interval(episodes),
        "conditions": {condition: summarize([e for e in episodes if e["condition"] == condition])
                       for condition in sorted({e["condition"] for e in episodes})},
        "episodes": episodes,
    })
    return seal(report)


def compare(reports):
    for report in reports:
        verify(report, "workflow-evaluation")
    if not reports:
        raise ValueError("No workflow runs")
    keys = ("protocol_hash", "dataset_sha256", "split", "max_steps")
    if any(any(r[key] != reports[0][key] for key in keys) for r in reports):
        raise ValueError("Workflow reports are not matched")
    configurations = [f"{r['candidate']['name']}/{r['strategy']}" for r in reports]
    if len(set(configurations)) != len(configurations):
        raise ValueError("Duplicate workflow configuration")
    baseline = next((r for r in reports if r["candidate"]["name"] == "rules" and r["strategy"] == "direct"), None)
    if baseline is None:
        raise ValueError("Include the executed rules baseline")
    rows = []
    for label, report in zip(configurations, reports):
        paired = interval(report["episodes"], baseline["episodes"])
        metrics = report["metrics"]
        rows.append({
            "configuration": label, "report_hash": report["report_hash"],
            "metrics": metrics, "uncertainty": report["uncertainty"],
            "paired_success_difference_vs_rules": paired,
            "meets_fixture_criterion_for_adding_stage": (
                paired["lower"] > 0 and metrics["unsafe_updates_executed"] == 0
                and metrics["primary_errors"] == 0
            ),
        })
    return seal({
        "kind": "workflow-comparison",
        **{key: reports[0][key] for key in keys},
        "rows": rows,
        "decision_criterion": "Paired 95% family-bootstrap improvement over rules above zero, no executed unsafe updates, and no inference errors. Applies only to this fixture; not production certification.",
        "notice": reports[0]["notice"],
    })
