"""Run the frozen benchmark and compare matched reports without a provider judge."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from .adapters import CandidateError, make_candidate
from .contract import ROOT, PROTOCOL, digest, load_dataset, normalize_answers, probability, request_for
from .metrics import quantile, select_threshold, summarize

WARMUP = {
    "state": "The message asks for the invoice total.",
    "questions": {"action": {"type": "choice", "instructions": "Choose an action.",
                              "criteria": {"read": "Read the invoice.", "write": "Modify the invoice."}}},
}


def protocol_hash():
    return digest([(name, (ROOT / name).read_text(encoding="utf-8")) for name in
                   ("contract.py", "metrics.py", "runner.py", "adapters.py", "local_models.py")])


def seal(report):
    report["report_hash"] = digest({k: v for k, v in report.items() if k != "report_hash"})
    return report


def verify(report, kind="decision-model-run"):
    if (report.get("kind") != kind or report.get("schema_version") != 1
            or report.get("report_hash") != digest({k: v for k, v in report.items() if k != "report_hash"})):
        raise ValueError("Invalid or modified benchmark report")
    return report


def run(name, split="holdout", *, device="cpu", trials=1, threshold=0.9, gate=None,
        input_price=None, hourly_cost=None, candidate=None):
    if type(trials) is not int or not 1 <= trials <= 10:
        raise ValueError("Use 1–10 trials")
    probability(threshold)
    for value in (input_price, hourly_cost):
        if value is not None and (type(value) not in (float, int) or not math.isfinite(value) or value < 0):
            raise ValueError("Cost assumptions must be finite and nonnegative")
    cases, manifest = load_dataset(split)
    start = time.perf_counter()
    fn, info, synchronize = candidate or make_candidate(name, device)
    initialization_ms = (time.perf_counter() - start) * 1000
    candidate_hash = digest(info)
    if gate is not None:
        verify(gate, "decision-model-gate")
        if split != "holdout" or gate["candidate_hash"] != candidate_hash:
            raise ValueError("Gate must be applied to the same candidate on holdout")
        if gate["protocol_hash"] != protocol_hash() or gate["dataset_version"] != manifest["version"]:
            raise ValueError("Gate protocol or dataset differs")
        if gate["calibration_hash"] != manifest["files"]["calibration"]["sha256"]:
            raise ValueError("Gate calibration split differs")
        if set(gate["groups"]) & {c["group"] for c in cases}:
            raise ValueError("Gate was fitted on overlapping groups")
        threshold = gate["threshold"]
    probe = {**copy.deepcopy(WARMUP), "model": info["model"]}
    probe_times = []
    # Warmup uses no benchmark case or label; failures abort setup, not a scored row.
    for _ in range(3):
        synchronize()
        started = time.perf_counter()
        output = fn(copy.deepcopy(probe))
        synchronize()
        normalize_answers(output, probe["questions"])
        if output.get("model") != info["model"]:
            raise CandidateError("model_version_mismatch")
        probe_times.append((time.perf_counter() - started) * 1000)
    rows, requests = [], []
    for trial in range(1, trials + 1):
        for case in cases:
            request = request_for(case, info["model"])
            error, answers, usage = None, {}, {}
            synchronize()
            started = time.perf_counter()
            try:
                payload = fn(copy.deepcopy(request))
                synchronize()
                if payload.get("model") != info["model"]:
                    raise CandidateError("model_version_mismatch")
                answers = normalize_answers(payload, request["questions"])
                raw_usage = payload.get("usage", {})
                for key in ("input_tokens", "output_tokens"):
                    value = raw_usage.get(key)
                    if value is not None:
                        if type(value) is not int or value < 0:
                            raise ValueError("Invalid token usage")
                        usage[key] = value
            except Exception as exc:
                synchronize()
                error = str(exc) if isinstance(exc, CandidateError) else type(exc).__name__
            elapsed = (time.perf_counter() - started) * 1000
            requests.append({"case_id": case["id"], "trial": trial, "latency_ms": elapsed,
                             "decision_count": len(case["questions"]), "usage": usage,
                             "error": error, "request_hash": digest(request)})
            for key, expected in case["expected"].items():
                answer = answers.get(key) if error is None else None
                probabilities = answer["probabilities"] if answer else None
                choice = answer["choice"] if answer else None
                rows.append({
                    "case_id": case["id"], "question_id": key, "group": case["group"],
                    "family": case["family"], "variant": case["variant"], "trial": trial,
                    "expected": expected["label"], "unsafe_labels": expected["unsafe_labels"],
                    "choice": choice, "probabilities": probabilities,
                    "provider_probability_sum": answer["provider_probability_sum"] if answer else None,
                    "provider_confidence": answer["provider_confidence"] if answer else None,
                    "p_max": max(probabilities.values()) if probabilities else None,
                    "correct": choice == expected["label"], "error": error,
                })
    times = [r["latency_ms"] for r in requests]
    total_tokens_known = all("input_tokens" in r["usage"] for r in requests)
    tokens = sum(r["usage"].get("input_tokens", 0) for r in requests)
    measured_seconds = sum(times) / 1000
    token_cost = tokens / 1_000_000 * input_price if input_price is not None and total_tokens_known else None
    compute_cost = measured_seconds / 3600 * hourly_cost if hourly_cost is not None else None
    slices = {}
    for dimension in ("family", "variant"):
        slices[dimension] = {value: summarize([r for r in rows if r[dimension] == value], threshold)
                             for value in sorted({r[dimension] for r in rows})}
    report = {
        "schema_version": 1, "kind": "decision-model-run", "protocol": PROTOCOL,
        "protocol_hash": protocol_hash(), "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate": info, "candidate_hash": candidate_hash,
        "dataset_version": manifest["version"], "dataset_hash": manifest["files"][split]["sha256"],
        "split": split, "groups": sorted({c["group"] for c in cases}),
        "trials": trials, "unique_requests": len(cases),
        "unique_decisions": sum(len(c["questions"]) for c in cases),
        "threshold": threshold, "threshold_statistic": "top_probability",
        "gate_report_hash": gate["report_hash"] if gate else None,
        "selection": "calibration" if gate else "fixed_before_run",
        "hardware": {"system": platform.system(), "machine": platform.machine()},
        "python": platform.python_version(),
        "initialization_ms_including_download_if_needed": initialization_ms,
        "warmup": {"requests": 3, "first_probe_ms": probe_times[0], "other_probe_ms": probe_times[1:],
                   "excluded_from_scores": True},
        "latency": {"unit": "request", "concurrency": 1, "p50_ms": quantile(times, 0.5),
                    "p95_ms": quantile(times, 0.95), "sum_seconds": measured_seconds,
                    "requests": len(requests),
                    "by_trial": {str(t): {"p50_ms": quantile([r["latency_ms"] for r in requests if r["trial"] == t], .5),
                                         "p95_ms": quantile([r["latency_ms"] for r in requests if r["trial"] == t], .95)}
                                 for t in range(1, trials + 1)}},
        "cost": {"input_usd_per_million_assumption": input_price,
                 "compute_usd_per_hour_assumption": hourly_cost,
                 "reported_input_tokens": tokens if total_tokens_known else None,
                 "estimated_input_charge_usd": token_cost,
                 "estimated_measured_compute_usd": compute_cost,
                 "scope": "Measured requests only. Warmup, setup, idle time, output charges, operations and fallback excluded. Null means unknown, not free."},
        "fallback": {"executed": False, "latency_ms": None, "cost_usd": None},
        "metrics": summarize(rows, threshold), "slices": slices, "requests": requests, "results": rows,
        "notice": manifest["limitations"] + " Repeated trials and variants are not independent samples. No production or safety certification.",
    }
    return seal(report)


def calibrate(report, max_error=0.05, min_accepted=10):
    verify(report)
    probability(max_error)
    if type(min_accepted) is not int or min_accepted < 1:
        raise ValueError("min_accepted must be a positive integer")
    if report["split"] != "calibration" or report["trials"] != 1:
        raise ValueError("Fit the gate on a calibration run with exactly one trial")
    if report["metrics"]["errors"]:
        raise ValueError("Resolve calibration execution errors before fitting a gate")
    threshold = select_threshold(report["results"], max_error, min_accepted)
    return seal({
        "kind": "decision-model-gate", "schema_version": 1,
        "candidate_hash": report["candidate_hash"], "protocol_hash": report["protocol_hash"],
        "dataset_version": report["dataset_version"], "calibration_hash": report["dataset_hash"],
        "source_report_hash": report["report_hash"], "groups": report["groups"],
        "threshold": threshold, "threshold_statistic": "top_probability",
        "max_empirical_error": max_error, "min_accepted": min_accepted,
        "calibration_metrics": summarize(report["results"], threshold),
        "notice": "Empirical threshold selection on a small calibration split; no guaranteed population error bound. Null threshold accepts nothing.",
    })


def compare(reports):
    if not reports:
        raise ValueError("Supply at least one report")
    for report in reports:
        verify(report)
    reference = reports[0]
    matched = ("protocol", "protocol_hash", "dataset_version", "dataset_hash", "split", "trials")
    if any(any(r[k] != reference[k] for k in matched) for r in reports):
        raise ValueError("Reports must use identical protocol, dataset, split and trial count")
    if len({r["candidate"]["name"] for r in reports}) != len(reports):
        raise ValueError("Duplicate candidate; compare one recorded configuration per candidate")
    if len({(r["selection"], r["threshold_statistic"]) for r in reports}) != 1:
        raise ValueError("Use the same threshold-selection method for every candidate")
    if reference["selection"] == "fixed_before_run" and len({r["threshold"] for r in reports}) != 1:
        raise ValueError("Fixed thresholds must match")
    candidates = {}
    for r in reports:
        candidates[r["candidate"]["name"]] = {
            "status": "completed" if not r["metrics"]["errors"] else "completed_with_errors",
            "report_hash": r["report_hash"], "model": r["candidate"]["model"],
            "revision": r["candidate"].get("revision"),
            "device": r["candidate"]["device"], "dtype": r["candidate"].get("dtype"),
            "threshold": r["threshold"], "metrics": r["metrics"], "latency": r["latency"],
            "cost": r["cost"], "gate_report_hash": r["gate_report_hash"],
        }
    for name in ("baseline", "strands", "laya", "jev"):
        candidates.setdefault(name, {"status": "not_run", "reason": "No matching recorded run supplied."})
    return seal({
        "schema_version": 1, "kind": "decision-model-comparison",
        **{k: reference[k] for k in matched},
        "unique_requests": reference["unique_requests"], "unique_decisions": reference["unique_decisions"],
        "groups": reference["groups"], "candidates": candidates,
        "notice": reference["notice"] + " Hardware, dtype and runtime differ unless explicitly matched. No fallback was executed.",
    })


def markdown(comparison):
    verify(comparison, "decision-model-comparison")
    def fmt(value, digits=3):
        return "—" if value is None else f"{value:.{digits}f}"
    lines = ["# Decision model comparison", "",
             f"Dataset: `{comparison['dataset_version']}` · split: **{comparison['split']}**",
             f"{comparison['unique_requests']} unique requests; {comparison['unique_decisions']} unique decisions; "
             f"{len(comparison['groups'])} scenario groups; {comparison['trials']} trial(s).", "",
             "| Candidate | Status | Accuracy | Brier | ECE | Coverage | Accepted error | Request p50 / p95 ms |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for name, candidate in comparison["candidates"].items():
        if candidate["status"] == "not_run":
            lines.append(f"| {name} | Not run | — | — | — | — | — | — |")
            continue
        m, latency = candidate["metrics"], candidate["latency"]
        lines.append(f"| {name} | {candidate['status']} | {fmt(m['accuracy'])} | {fmt(m['brier_multiclass'])} "
                     f"| {fmt(m['ece_10_equal_width'])} | {fmt(m['coverage'])} | {fmt(m['accepted_error_rate'])} "
                     f"| {fmt(latency['p50_ms'], 1)} / {fmt(latency['p95_ms'], 1)} |")
    lines += ["", "## Interpretation", "", comparison["notice"],
              "", "Coverage is the fraction accepted using top probability. Abstained and failed decisions require a fallback; "
              "fallback latency, quality and cost have not been measured. Costs remain unknown unless explicit assumptions were supplied.",
              "", "No Jev comparison is established by an unexecuted adapter. The full JSON reports retain per-case outputs, "
              "probabilities, errors, model revisions, threshold provenance, and per-request timing.", ""]
    return "\n".join(lines)
