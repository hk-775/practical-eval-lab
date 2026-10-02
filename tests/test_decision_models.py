import copy
import json
import math

import pytest

from benchmarks.decision_models import adapters
from benchmarks.decision_models.build_cases import artifacts
from benchmarks.decision_models.contract import (
    ROOT, digest, load_dataset, normalize_answers, read_json, request_for,
)
from benchmarks.decision_models.metrics import quantile, select_threshold, summarize
from benchmarks.decision_models.runner import (
    WARMUP, calibrate, compare, markdown, protocol_hash, run, seal, verify,
)


def test_frozen_cases_group_split_and_no_reference_in_request():
    for name, text in artifacts().items():
        assert (ROOT / "data" / name).read_bytes() == text.encode()
    calibration, manifest = load_dataset("calibration")
    holdout, _ = load_dataset("holdout")
    assert len(calibration) == 24 and len(holdout) == 48
    assert sum(len(c["questions"]) for c in holdout) == 64
    assert not ({c["group"] for c in calibration} & {c["group"] for c in holdout})
    assert manifest["version"] == "enterprise-decisions-synthetic-v1"
    for case in calibration + holdout:
        request = request_for(case, "model-v1")
        assert set(request) == {"state", "questions", "model"}
        assert "expected" not in request and "group" not in request
    # Every option-order variant preserves the reference while changing order.
    by_id = {case["id"]: case for case in holdout}
    for case in holdout:
        if case["variant"] == "options_reversed":
            original = by_id[case["group"] + "-original"]
            assert case["expected"] == original["expected"]
            for key in case["questions"]:
                assert list(case["questions"][key]["criteria"]) == list(reversed(original["questions"][key]["criteria"]))


def response(probabilities=None, choice="read"):
    return {"model": "fixture-v1", "answers": {"action": {
        "type": "choice", "choice": choice,
        "probabilities": probabilities or {"read": .8, "write": .2},
    }}}


@pytest.mark.parametrize("probabilities,choice", [
    ({"read": float("nan"), "write": .2}, "read"),
    ({"read": float("inf"), "write": .2}, "read"),
    ({"read": -.1, "write": 1.1}, "write"),
    ({"read": .8, "write": .8}, "read"),
    ({"read": .8, "other": .2}, "read"),
    ({"read": .8, "write": .2}, "write"),
    ({"read": True, "write": 0}, "read"),
])
def test_reject_malformed_or_inconsistent_predictions(probabilities, choice):
    with pytest.raises(ValueError):
        normalize_answers(response(probabilities, choice), WARMUP["questions"])


def test_rounding_tolerance_recorded_and_provider_confidence_not_used_as_probability():
    payload = response({"read": .8000, "write": .1999})
    payload["answers"]["action"]["confidence"] = .6
    result = normalize_answers(payload, WARMUP["questions"])["action"]
    assert result["provider_probability_sum"] == pytest.approx(.9999)
    assert sum(result["probabilities"].values()) == pytest.approx(1)
    assert result["provider_confidence"] == .6
    for bad in ({"answers": {}}, {"answers": {"action": {}, "extra": {}}}):
        with pytest.raises(ValueError):
            normalize_answers(bad, WARMUP["questions"])


def metric_row(p, expected="a", error=None):
    choice = max(p, key=p.get) if p else None
    return {"probabilities": p, "choice": choice, "expected": expected,
            "correct": choice == expected, "error": error,
            "p_max": max(p.values()) if p else None, "unsafe_labels": ["b"]}


def test_metrics_failures_denominators_calibration_and_abstention():
    rows = [metric_row({"a": .9, "b": .1}), metric_row({"a": .2, "b": .8}),
            metric_row(None, error="timeout"), metric_row({"a": .05, "b": .95})]
    m = summarize(rows, .9)
    assert m["accuracy"] == .25
    assert m["valid_decisions"] == 3 and m["errors"] == 1
    assert m["coverage"] == .5 and m["accepted_error_rate"] == .5
    assert m["accepted_unsafe_rate"] == .25
    assert m["fallback_required"] == 2
    assert m["brier_multiclass"] == pytest.approx((.02 + 1.28 + 1.805) / 3)
    assert m["nll"] == pytest.approx((-math.log(.9) - math.log(.2) - math.log(.05)) / 3)
    assert m["ece_10_equal_width"] == pytest.approx(.55)
    assert summarize(rows, None)["accepted_error_rate"] is None
    assert summarize([], .9)["accuracy"] is None
    assert quantile([10, 20, 30], .95) == pytest.approx(29)
    assert select_threshold(rows, 0, 2) is None


def baseline_candidate():
    return adapters.lexical, {"name": "baseline", "model": "fixture-v1", "device": "cpu"}, lambda: None


def test_calibration_holdout_gate_and_comparison_identity():
    calibration = run("baseline", "calibration", candidate=baseline_candidate())
    gate = calibrate(calibration)
    report = run("baseline", "holdout", gate=gate, candidate=baseline_candidate())
    assert report["selection"] == "calibration" and report["threshold"] is None
    assert report["metrics"]["decisions"] == 64
    assert report["latency"]["requests"] == 48
    assert report["warmup"]["requests"] == 3
    assert report["fallback"]["executed"] is False
    assert report["cost"]["estimated_measured_compute_usd"] is None
    assert report["cost"]["reported_input_tokens"] is None
    with pytest.raises(ValueError):
        calibrate(report)
    with pytest.raises(ValueError):
        run("baseline", "calibration", gate=gate, candidate=baseline_candidate())
    other = copy.deepcopy(gate)
    other["candidate_hash"] = "different"
    seal(other)
    with pytest.raises(ValueError):
        run("baseline", "holdout", gate=other, candidate=baseline_candidate())
    comparison = compare([report])
    assert comparison["candidates"]["jev"]["status"] == "not_run"
    assert "| jev | Not run |" in markdown(comparison)
    with pytest.raises(ValueError):
        compare([calibration, report])
    with pytest.raises(ValueError):
        compare([report, report])
    report["metrics"]["accuracy"] = 1.0
    with pytest.raises(ValueError):
        verify(report)


def test_execution_errors_are_recorded_without_exception_bodies():
    calls = 0
    def failing(request):
        nonlocal calls
        calls += 1
        if calls <= 3:
            return adapters.lexical(request)
        raise RuntimeError("SECRET credential or private provider response")
    report = run("baseline", candidate=(failing, baseline_candidate()[1], lambda: None))
    assert report["metrics"]["errors"] == 64
    assert report["metrics"]["accuracy"] == 0
    assert report["metrics"]["brier_multiclass"] is None
    assert "SECRET" not in json.dumps(report)
    assert all(row["error"] == "RuntimeError" for row in report["results"])


def test_jev_requires_key_before_network_and_does_not_retry_or_redirect(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(adapters, "build_opener", lambda *args: pytest.fail("Network setup before key"))
    with pytest.raises(adapters.CandidateError, match="not_run_missing_api_key"):
        adapters.make_candidate("jev")
    with pytest.raises(adapters.CandidateError, match="redirect_rejected"):
        adapters.NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.invalid")


def test_jev_request_and_response_contract_without_real_credentials(monkeypatch):
    calls = []
    class Reply:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, limit):
            return json.dumps(response()).encode()
    class Opener:
        def open(self, req, timeout):
            calls.append((req, timeout))
            return Reply()
    monkeypatch.setenv("TYPESAFE_API_KEY", "fixture-test-value")
    monkeypatch.setattr(adapters, "build_opener", lambda *args: Opener())
    fn, info, _ = adapters.make_candidate("jev")
    output = fn({**WARMUP, "model": "jev-1.13.0"})
    assert len(calls) == 1
    request, timeout = calls[0]
    assert json.loads(request.data)["model"] == "jev-1.13.0"
    assert timeout == 60
    assert request.get_header("Authorization") == "Bearer fixture-test-value"
    assert "fixture-test-value" not in json.dumps(info)
    assert normalize_answers(output, WARMUP["questions"])["action"]["choice"] == "read"


@pytest.mark.parametrize("name", ["baseline", "strands", "laya"])
def test_published_evidence_recomputes_from_frozen_cases_and_outputs(name):
    directory = ROOT / "recordings/2026-10-02"
    calibration = verify(read_json(directory / f"{name}-calibration.json"))
    gate = verify(read_json(directory / f"{name}-gate.json"), "decision-model-gate")
    holdout = verify(read_json(directory / f"{name}-holdout.json"))
    assert calibration["protocol_hash"] == holdout["protocol_hash"] == protocol_hash()
    assert gate["source_report_hash"] == calibration["report_hash"]
    assert gate["threshold"] == select_threshold(calibration["results"], .05, 10)
    assert holdout["gate_report_hash"] == gate["report_hash"]
    assert holdout["threshold"] == gate["threshold"]
    assert calibration["candidate_hash"] == holdout["candidate_hash"] == digest(holdout["candidate"])
    assert holdout["trials"] == 3 and holdout["unique_decisions"] == 64
    assert holdout["metrics"]["errors"] == 0
    assert not holdout["fallback"]["executed"]
    for report in (calibration, holdout):
        cases, manifest = load_dataset(report["split"])
        by_id = {case["id"]: case for case in cases}
        assert report["dataset_hash"] == manifest["files"][report["split"]]["sha256"]
        assert len(report["requests"]) == len(cases) * report["trials"]
        for request in report["requests"]:
            assert request["request_hash"] == digest(
                request_for(by_id[request["case_id"]], report["candidate"]["model"]))
        for row in report["results"]:
            case = by_id[row["case_id"]]
            assert row["expected"] == case["expected"][row["question_id"]]["label"]
            assert row["unsafe_labels"] == case["expected"][row["question_id"]]["unsafe_labels"]
            assert row["correct"] == (row["choice"] == row["expected"])
            assert row["p_max"] == max(row["probabilities"].values())
        recomputed = summarize(report["results"], report["threshold"])
        for key in ("accuracy", "coverage", "accepted_error_rate", "brier_multiclass", "nll",
                    "ece_10_equal_width", "accepted_unsafe_rate", "fallback_required"):
            if recomputed[key] is None:
                assert report["metrics"][key] is None
            else:
                assert recomputed[key] == pytest.approx(report["metrics"][key])
        assert quantile([r["latency_ms"] for r in report["requests"]], .95) == pytest.approx(report["latency"]["p95_ms"])
    reports = [read_json(directory / f"{candidate}-holdout.json")
               for candidate in ("baseline", "strands", "laya")]
    assert compare(reports) == read_json(directory / "comparison.json")
