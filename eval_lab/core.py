"""Shared dataset validation, evaluation reports, and matched comparisons."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import __version__
from .candidates import make_candidate
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
        if not isinstance(case["input"], str) or not case["input"].strip() or len(case["input"]) > 5000:
            raise ValueError(f"{case['id']}: input must contain 1–5000 characters")
        tags = case["tags"]
        if not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip() or len(t) > 60 for t in tags):
            raise ValueError(f"{case['id']}: tags must be nonempty strings")
        if len(tags) > 20 or len(tags) != len(set(tags)):
            raise ValueError(f"{case['id']}: use at most 20 distinct tags")
        validate_expected(suite, case["expected"])
    return cases


def load_cases(suite: str, split: str = "dev", path: Path | None = None) -> list[dict]:
    suite_info(suite)
    if split not in ("dev", "holdout"):
        raise ValueError("split must be dev or holdout")
    path = path or DATA / suite / f"{split}.jsonl"
    try:
        cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
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
             runner: Callable | None = None) -> dict:
    cases = load_cases(suite, split) if cases is None else validate_cases(suite, cases)
    settings = settings_for(suite, settings)
    threshold = threshold_value(threshold)
    fn, candidate_info = make_candidate(suite, candidate, model=model, prompt=prompt)
    if runner is not None:
        fn, candidate_info = runner, {"name": "custom", "kind": "injected_callable"}
    results, buckets = [], defaultdict(list)
    for case in cases:
        start = time.perf_counter()
        error = None
        try:
            actual = fn(case["input"])
            json.dumps(actual, allow_nan=False)  # Ensure reports remain serializable.
            verdict = grade(suite, actual, case["expected"], settings)
        except Exception as exc:
            actual = None
            # Provider exceptions can contain request data; do not publish their message.
            error = type(exc).__name__
            verdict = {"passed": False, "checks": [{"name": "execution", "passed": False, "detail": f"Candidate failed ({error})"}]}
        result = {**case, "actual": actual, **verdict, "error": error,
                  "latency_ms": round((time.perf_counter() - start) * 1000, 3)}
        results.append(result)
        for tag in case["tags"]:
            buckets[tag].append(result["passed"])
    passed = sum(r["passed"] for r in results)
    return {
        "schema_version": 1, "lab_version": __version__, "suite": suite, "split": split,
        "created_at": datetime.now(timezone.utc).isoformat(), "candidate": candidate_info,
        "dataset_hash": digest(cases),
        "grader_hash": digest({"settings": settings, "source": Path(__file__).with_name("suites.py").read_text()}),
        "settings": settings, "threshold": threshold, "score": passed / len(cases),
        "passed": passed, "failed": len(cases) - passed, "total": len(cases),
        "passed_gate": passed / len(cases) >= threshold,
        "slices": {tag: {"passed": sum(values), "total": len(values), "accuracy": sum(values) / len(values)}
                   for tag, values in sorted(buckets.items())},
        "results": results,
    }


def compare_reports(before: dict, after: dict) -> dict:
    for key in ("schema_version", "suite", "split", "dataset_hash", "grader_hash", "threshold"):
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
    return {
        "before": before, "after": after,
        "delta": after["score"] - before["score"],
        "improved": sum(c["change"] == "improved" for c in changes),
        "regressed": sum(c["change"] == "regressed" for c in changes),
        "changes": changes,
    }
