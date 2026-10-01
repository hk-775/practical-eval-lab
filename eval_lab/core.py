"""Shared dataset validation, evaluation reports, and matched comparisons."""

from __future__ import annotations

import hashlib
import copy
import json
import math
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import __version__
from .candidates import make_candidate
from .integrations import CandidateOutput, configured_candidate
from . import advanced
from .suites import DATA, grade, settings_for, suite_info, validate_expected


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def validate_cases(suite: str, cases: list) -> list[dict]:
    suite_info(suite)
    if not isinstance(cases, list) or not 1 <= len(cases) <= 500:
        raise ValueError("A dataset must contain 1–500 cases")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "input", "expected", "tags"}:
            raise ValueError("Each case must contain exactly id, input, expected, and tags")
        if not isinstance(case["id"], str) or not case["id"].strip() or len(case["id"]) > 100:
            raise ValueError("Case IDs must be nonempty strings of at most 100 characters")
        if case["id"] in ids:
            raise ValueError(f"Duplicate case ID: {case['id']}")
        ids.add(case["id"])
        if suite in advanced.CATALOG:
            advanced.validate_input(suite, case["input"])
        elif not isinstance(case["input"], str) or not case["input"].strip():
            raise ValueError(f"{case['id']}: input must be a nonempty string")
        if len(json.dumps(case["input"], ensure_ascii=False, allow_nan=False)) > 20000:
            raise ValueError(f"{case['id']}: input must fit in 20,000 characters")
        tags = case["tags"]
        if not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip() or len(t) > 60 for t in tags):
            raise ValueError(f"{case['id']}: tags must be nonempty strings")
        if len(tags) > 20 or len(tags) != len(set(tags)):
            raise ValueError(f"{case['id']}: use at most 20 distinct tags")
        validate_expected(suite, case["expected"])
        if suite in advanced.CATALOG:
            advanced.validate_reference(suite, case["input"], case["expected"])
    return cases


def load_cases(suite: str, split: str = "dev", path: Path | None = None) -> list[dict]:
    suite_info(suite)
    if split not in ("dev", "holdout"):
        raise ValueError("split must be dev or holdout")
    path = path or DATA / suite / f"{split}.jsonl"
    try:
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSONL in {path.name}: {exc.msg}") from exc
    return validate_cases(suite, cases)


def threshold_value(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("threshold must be a finite number from 0 to 1")
    return float(value)


def run_eval(suite: str, candidate: str = "baseline", split: str = "dev", *,
             cases: list[dict] | None = None, settings: dict | None = None,
             threshold: float = 0.8, model: str | None = None, prompt: str | None = None,
             runner: Callable | None = None, project: dict | None = None,
             trials: int = 1, gates: dict | None = None, swap_pairs: bool = False) -> dict:
    cases = load_cases(suite, split) if cases is None else validate_cases(suite, cases)
    if split not in ("dev", "holdout"):
        raise ValueError("split must be dev or holdout")
    if type(trials) is not int or not 1 <= trials <= 20 or trials * len(cases) > 5000:
        raise ValueError("Use 1–20 trials and at most 5,000 executions per run")
    if swap_pairs:
        if suite != "response_quality":
            raise ValueError("Pair swapping is only available for response_quality")
        cases = copy.deepcopy(cases)
        for case in cases:
            value = case["input"]
            value["A"], value["B"] = value["B"], value["A"]
            case["expected"]["winner"] = "B" if case["expected"]["winner"] == "A" else "A"
    settings = settings_for(suite, settings)
    threshold = threshold_value(threshold)
    gates = gate_settings(gates)
    tags = {tag for c in cases for tag in c["tags"]}
    if (set(gates["critical_tags"]) | set(gates["min_slices"])) - tags:
        raise ValueError("Gate tags must exist in the dataset")
    if runner is not None:
        fn, candidate_info = runner, {"name": candidate if candidate != "baseline" else "custom", "kind": "injected_callable"}
    elif project and candidate in project:
        fn, candidate_info = configured_candidate(suite, candidate, project[candidate])
    else:
        fn, candidate_info = make_candidate(suite, candidate, model=model, prompt=prompt)
    results, buckets = [], defaultdict(list)
    for trial in range(1, trials + 1):
        for case in cases:
            start = time.perf_counter()
            error, usage, metadata, candidate_ms, grader_ms = None, {}, {}, 0, 0
            try:
                actual = fn(copy.deepcopy(case["input"]))
                candidate_ms = (time.perf_counter() - start) * 1000
                if isinstance(actual, CandidateOutput):
                    usage = valid_usage(actual.usage)
                    metadata = {k: v for k, v in actual.metadata.items()
                                if k in ("model", "response_id") and isinstance(v, str) and len(v) <= 200}
                    actual = actual.output
                json.dumps(actual, allow_nan=False)
                grade_start = time.perf_counter()
                verdict = grade(suite, actual, case["expected"], settings, case["input"])
                grader_ms = (time.perf_counter() - grade_start) * 1000
            except Exception as exc:
                candidate_ms = candidate_ms or (time.perf_counter() - start) * 1000
                actual = None
                # Provider exceptions can contain credentials or private request data.
                error = type(exc).__name__
                verdict = {"passed": False, "checks": [{"name": "execution", "passed": False, "detail": f"Candidate failed ({error})"}]}
            result = {**copy.deepcopy(case), "case_id": case["id"], "trial": trial,
                      "id": case["id"] if trials == 1 else f"{case['id']}::trial-{trial}",
                      "actual": actual, **verdict, "error": error, "usage": usage, "metadata": metadata,
                      "candidate_latency_ms": round(candidate_ms, 3), "grader_latency_ms": round(grader_ms, 3),
                      "latency_ms": round((time.perf_counter() - start) * 1000, 3)}
            results.append(result)
            for tag in case["tags"]:
                buckets[tag].append(result["passed"])
    passed = sum(r["passed"] for r in results)
    slices = {tag: {"passed": sum(values), "total": len(values), "accuracy": sum(values) / len(values)}
              for tag, values in sorted(buckets.items())}
    gate_results = [{"name": "overall", "passed": passed / len(results) >= threshold, "detail": f"Overall score >= {threshold:.0%}"}]
    gate_results += [{"name": f"critical:{tag}", "passed": slices[tag]["accuracy"] == 1, "detail": "Every critical execution must pass"} for tag in gates["critical_tags"]]
    gate_results += [{"name": f"slice:{tag}", "passed": slices[tag]["accuracy"] >= minimum, "detail": f"Slice score >= {minimum:.0%}"} for tag, minimum in gates["min_slices"].items()]
    report = {
        "schema_version": 2, "lab_version": __version__, "suite": suite, "split": split,
        "created_at": datetime.now(timezone.utc).isoformat(), "candidate": candidate_info,
        "dataset_hash": digest(cases),
        "grader_hash": digest({"settings": settings, "source": [Path(__file__).with_name(f).read_text(encoding="utf-8") for f in ("suites.py", "advanced.py", "core.py")]}),
        "settings": settings, "threshold": threshold, "score": passed / len(results),
        "passed": passed, "failed": len(results) - passed, "total": len(results),
        "passed_gate": all(g["passed"] for g in gate_results), "gate_policy": gates, "gates": gate_results,
        "slices": slices, "results": results, "trials": trials, "case_count": len(cases),
        "pair_order": "swapped" if swap_pairs else "original",
        "execution_errors": sum(r["error"] is not None for r in results),
        "data_notice": data_notice(suite),
    }
    report["metrics"] = aggregate_metrics(suite, results, trials)
    return report


def data_notice(suite):
    if suite != "response_quality":
        return "Bundled cases are synthetic teaching data under MIT-0. Custom cases may have different provenance."
    return ("Bundled human-preference source: Anthropic HH-RLHF, helpful-base/test.jsonl.gz, "
            "revision c72f5cee8eb7b4d2ea5617657f4430d5e333af07. "
            "Custom cases may have different provenance. Original data and its reproductions retain this notice:\n\n"
            + (DATA / "response_quality" / "LICENSE.txt").read_text(encoding="utf-8"))


def valid_usage(value):
    if not isinstance(value, dict) or set(value) - {"input_tokens", "output_tokens", "total_tokens"}:
        raise ValueError("Usage supports input_tokens, output_tokens, total_tokens")
    if any(type(v) is not int or v < 0 for v in value.values()):
        raise ValueError("Token counts must be nonnegative integers")
    return value


def gate_settings(value=None):
    value = {} if value is None else value
    if not isinstance(value, dict) or set(value) - {"critical_tags", "min_slices", "fail_on_regression"}:
        raise ValueError("Unknown gate policy")
    critical, slices = value.get("critical_tags", []), value.get("min_slices", {})
    if not isinstance(critical, list) or any(not isinstance(t, str) or not t for t in critical):
        raise ValueError("critical_tags must list tag names")
    if not isinstance(slices, dict) or any(not isinstance(t, str) or not t for t in slices):
        raise ValueError("min_slices must map tags to thresholds")
    if type(value.get("fail_on_regression", False)) is not bool:
        raise ValueError("fail_on_regression must be a boolean")
    return {"critical_tags": sorted(set(critical)), "min_slices": {t: threshold_value(n) for t, n in slices.items()},
            "fail_on_regression": value.get("fail_on_regression", False)}


def aggregate_metrics(suite, results, trials):
    checks, measurements, case_scores = defaultdict(list), defaultdict(list), defaultdict(list)
    usage = defaultdict(int)
    for r in results:
        for check in r["checks"]:
            checks[check["name"]].append(check["passed"])
        for key, value in r.get("metrics", {}).items():
            measurements[key].append(value)
        for key, value in r["usage"].items():
            usage[key] += value
        case_scores[r["case_id"]].append(r["passed"])
    latencies = sorted(r["candidate_latency_ms"] for r in results)
    output = {
        "checks": {key: {"passed": sum(values), "total": len(values), "rate": sum(values) / len(values)} for key, values in checks.items()},
        "measurements": {key: {"mean": statistics.mean(values), "count": len(values)} for key, values in measurements.items()},
        "candidate_latency_ms": {"median": statistics.median(latencies), "p95": latencies[math.ceil(.95 * len(latencies)) - 1]},
        "usage": dict(usage), "usage_coverage": sum(bool(r["usage"]) for r in results),
        "trial_scores": [statistics.mean(r["passed"] for r in results if r["trial"] == t) for t in range(1, trials + 1)],
        "unstable_cases": sum(len(set(v)) > 1 for v in case_scores.values()),
    }
    if suite == "classification":
        labels = ["Hardware", "Software", "Other"]
        matrix = {label: {p: 0 for p in labels + ["invalid"]} for label in labels}
        for r in results:
            raw = r["actual"]
            predicted = next((label for label in labels if isinstance(raw, str) and raw.strip().casefold() == label.casefold()), "invalid")
            matrix[r["expected"]][predicted] += 1
        f1 = []
        for label in labels:
            tp = matrix[label][label]
            fp = sum(matrix[other][label] for other in labels if other != label)
            fn = sum(n for p, n in matrix[label].items() if p != label)
            f1.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0)
        output.update(confusion_matrix=matrix, macro_f1=statistics.mean(f1))
    return output


def compare_reports(before: dict, after: dict) -> dict:
    for key in ("schema_version", "suite", "split", "dataset_hash", "grader_hash", "threshold", "trials", "gate_policy"):
        if before.get(key) != after.get(key):
            raise ValueError(f"Cannot compare runs with different {key}; rerun both on the same configuration")
    old, new = {r["id"]: r for r in before["results"]}, {r["id"]: r for r in after["results"]}
    if old.keys() != new.keys():
        raise ValueError("Cannot compare different case IDs")
    changes = []
    for key, current in new.items():
        previous = old[key]
        change = ("improved" if current["passed"] else "regressed") if previous["passed"] != current["passed"] else "unchanged"
        changes.append({"id": key, "change": change, "before": previous, "after": current})
    regressed = sum(c["change"] == "regressed" for c in changes)
    gates = list(after["gates"])
    if after["gate_policy"]["fail_on_regression"]:
        gates.append({"name": "regressions", "passed": regressed == 0, "detail": f"{regressed} regressions; none allowed"})
    return {
        "before": before, "after": after,
        "delta": after["score"] - before["score"],
        "improved": sum(c["change"] == "improved" for c in changes),
        "regressed": regressed, "changes": changes, "gates": gates,
        "passed_gate": all(g["passed"] for g in gates),
    }
