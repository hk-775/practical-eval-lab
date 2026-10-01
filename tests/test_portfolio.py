import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval_lab.advanced import ReturnSimulator, judge_pair, run_agent
from eval_lab.cli import main
from eval_lab.core import compare_reports, load_cases, run_eval, validate_cases
from eval_lab.integrations import CandidateOutput, configured_candidate, load_project, validate_spec
from eval_lab.reports import ReportStore, html_report, validate_report
from eval_lab.store import validate_config
from eval_lab.suites import grade, settings_for


def verdict(suite, actual, case):
    return grade(suite, actual, case["expected"], settings_for(suite), case["input"])


def test_rag_checks_retrieval_answer_and_evidence_separately():
    case = load_cases("rag")[0]
    output = {"retrieved_ids": ["returns"], "answer": case["expected"]["answer"], "citations": ["returns"]}
    assert verdict("rag", output, case)["passed"]
    output["citations"] = ["labels"]
    failed = {c["name"] for c in verdict("rag", output, case)["checks"] if not c["passed"]}
    assert failed == {"citations", "evidence"}
    output["citations"] = ["returns"]
    output["answer"] += " Also everything is free."
    failed = {c["name"] for c in verdict("rag", output, case)["checks"] if not c["passed"]}
    assert {"answer", "evidence"} <= failed


def test_rag_rejects_unknown_reference_documents_and_bad_abstention():
    case = load_cases("rag")[4]
    assert verdict("rag", {"retrieved_ids": [], "answer": None, "citations": []}, case)["passed"]
    assert not verdict("rag", {"retrieved_ids": [], "answer": "", "citations": []}, case)["passed"]
    case["expected"] = {"relevant_ids": ["invented"], "answer": "invented"}
    with pytest.raises(ValueError, match="Relevant"):
        validate_cases("rag", [case])


def test_agent_replay_rejects_forged_results_and_outcomes():
    case = load_cases("agent")[0]
    actual = run_agent(case["input"], True)
    assert verdict("agent", actual, case)["passed"]
    forged = copy.deepcopy(actual)
    forged["trace"][0]["result"] = {"found": False}
    assert not verdict("agent", forged, case)["passed"]
    actual["final"] = "declined"
    failed = {c["name"] for c in verdict("agent", actual, case)["checks"] if not c["passed"]}
    assert failed == {"final_state"}
    actual = {"trace": [], "final": "returned"}
    assert not verdict("agent", actual, case)["passed"]


def test_agent_rejects_skipped_checks_duplicate_returns_and_over_budget():
    case = load_cases("agent")[0]
    sim = ReturnSimulator(case["input"])
    args = {"order_id": case["input"]["order"]["id"]}
    with pytest.raises(ValueError, match="unauthorized"):
        sim.call("create_return", args)
    sim = ReturnSimulator(case["input"])
    for tool in ("lookup_order", "check_eligibility", "create_return"):
        sim.call(tool, args)
    with pytest.raises(ValueError, match="duplicated"):
        sim.call("create_return", args)
    output = run_agent(case["input"], True)
    output["trace"] *= 3
    checks = verdict("agent", output, case)["checks"]
    assert not next(c["passed"] for c in checks if c["name"] == "budget")


def test_agent_retries_and_respects_unsupported_requests():
    case = load_cases("agent")[4]
    old, new = run_agent(case["input"]), run_agent(case["input"], True)
    assert not verdict("agent", old, case)["passed"]
    assert verdict("agent", new, case)["passed"]
    assert len(new["trace"]) == 4
    case = load_cases("agent")[6]
    assert run_agent(case["input"], True) == {"trace": [], "final": "no_action"}
    case = load_cases("agent")[7]
    assert not verdict("agent", {"trace": [], "final": "unavailable"}, case)["passed"]
    assert not verdict("agent", run_agent(case["input"]), case)["passed"]
    assert verdict("agent", run_agent(case["input"], True), case)["passed"]


def test_pairwise_labels_are_not_passed_to_candidates_and_swaps_are_correct():
    cases = load_cases("response_quality")[:1]
    seen = []
    def candidate(value):
        seen.append(copy.deepcopy(value))
        return judge_pair(value, True)
    original = run_eval("response_quality", cases=cases, runner=candidate)
    swapped = run_eval("response_quality", cases=cases, runner=candidate, swap_pairs=True)
    assert set(seen[0]) == {"conversation", "A", "B"}
    assert seen[1]["A"] == seen[0]["B"]
    assert swapped["results"][0]["expected"]["winner"] != original["results"][0]["expected"]["winner"]
    with pytest.raises(ValueError, match="dataset_hash"):
        compare_reports(original, swapped)


def test_repeated_trials_keep_case_count_usage_and_variability():
    calls = 0
    def variable(_):
        nonlocal calls
        calls += 1
        return CandidateOutput("Hardware" if calls % 2 else "Other", {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3})
    report = run_eval("classification", cases=load_cases("classification")[:1], runner=variable, trials=4)
    assert report["case_count"] == 1 and report["total"] == 4 and report["score"] == .5
    assert report["metrics"]["trial_scores"] == [1, 0, 1, 0]
    assert report["metrics"]["unstable_cases"] == 1
    assert report["metrics"]["usage"]["total_tokens"] == 12
    validate_report(report)
    with pytest.raises(ValueError, match="trials"):
        run_eval("classification", trials=True)


def test_candidate_cannot_mutate_the_dataset_or_reference():
    cases = load_cases("agent")[:1]
    original = copy.deepcopy(cases)
    def mutates(value):
        value["order"]["age_days"] = 400
        return {"trace": [], "final": "declined"}
    run_eval("agent", cases=cases, runner=mutates)
    assert cases == original


def test_regression_slice_and_critical_gates_block_average_improvement():
    gates = {"fail_on_regression": True, "critical_tags": ["vocabulary"], "min_slices": {"lookup": 1}}
    before = run_eval("tool_calling", "baseline", "holdout", gates=gates)
    after = run_eval("tool_calling", "improved", "holdout", gates=gates)
    output = compare_reports(before, after)
    assert output["delta"] > 0 and after["score"] >= .8
    assert not output["passed_gate"]
    assert {g["name"] for g in output["gates"] if not g["passed"]} == {"regressions", "critical:vocabulary", "slice:lookup"}
    with pytest.raises(ValueError, match="tags must exist"):
        run_eval("classification", gates={"min_slices": {"nonexistent": .1}})


def test_cli_distinguishes_quality_config_and_execution_failures(tmp_path, monkeypatch):
    assert main(["compare", "--suite", "tool_calling", "--split", "holdout", "--fail-on-regression"]) == 1
    assert main(["run", "--trials", "0"]) == 2
    def raises(*_):
        raise RuntimeError("secret message")
    monkeypatch.setattr("eval_lab.core.make_candidate", lambda *a, **k: (raises, {"name": "failed", "kind": "test"}))
    assert main(["run", "--min-score", "0"]) == 3


@pytest.mark.parametrize("encoding", ["ascii", "cp1252"])
def test_cli_exports_unicode_cases_with_legacy_console_encoding(tmp_path, encoding):
    cases = load_cases("classification")[:1]
    cases[0].update(id="café-東京", tags=["révision"])
    cases_path, report_path = tmp_path / "cases.jsonl", tmp_path / "report.json"
    cases_path.write_text(json.dumps(cases[0], ensure_ascii=False) + "\n", encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": encoding}
    result = subprocess.run(
        [sys.executable, "-m", "eval_lab", "compare", "--cases", str(cases_path),
         "--critical-tag", "révision", "--report", str(report_path)],
        env=env, capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode(encoding)
    assert "\\u2192" in result.stdout.decode(encoding)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["after"]["results"][0]["id"] == "café-東京"
    assert report["passed_gate"]
    invalid = subprocess.run(
        [sys.executable, "-m", "eval_lab", "run", "--min-slice", "東京=1"],
        env=env, capture_output=True,
    )
    assert invalid.returncode == 2
    assert "tags must exist" in invalid.stderr.decode(encoding)


def test_named_python_candidates_are_available_without_runner_changes():
    project = load_project(Path("examples/python-project.json"))
    output = compare_reports(run_eval("classification", "app-v1", project=project),
                             run_eval("classification", "app-v2", project=project))
    assert output["before"]["candidate"]["name"] == "app-v1"
    assert output["delta"] > 0
    with pytest.raises(ValueError, match="not registered"):
        run_eval("agent", "app-v1", project=project)


@pytest.mark.parametrize("spec", [
    {"kind": "http", "url": "http://remote.invalid"},
    {"kind": "http", "url": "https://user:secret@example.invalid"},
    {"kind": "http", "url": "https://example.invalid?key=secret"},
    {"kind": "http", "url": "https://example.invalid", "token": "secret"},
    {"kind": "http", "url": "https://example.invalid", "timeout": True},
    {"kind": "python", "target": "__import__('os')"},
])
def test_integrations_reject_unsafe_or_ambiguous_configuration(spec):
    with pytest.raises(ValueError):
        validate_spec(spec)


def test_openai_adapter_preserves_usage_without_live_call(monkeypatch):
    received = []
    class FakeOpenAI:
        def __init__(self, **kwargs):
            assert kwargs == {"timeout": 30, "max_retries": 0}
            self.responses = self
        def create(self, **kwargs):
            received.append(kwargs)
            return SimpleNamespace(output_text='{"winner":"A","reason":"test"}',
                                   usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
                                   model="test-model-snapshot", id="test-response")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    report = run_eval("response_quality", "openai", model="test-model", cases=load_cases("response_quality")[:1])
    assert report["metrics"]["usage"]["total_tokens"] == 15
    assert report["results"][0]["metadata"]["model"] == "test-model-snapshot"
    assert "expected" not in json.loads(received[0]["input"][1]["content"])
    assert "test-only-key" not in json.dumps(report)


def test_versioned_profiles_accept_legacy_but_reject_cross_suite_import():
    legacy = {"cases": load_cases("classification"), "settings": {}, "threshold": .8}
    current = validate_config("classification", legacy)
    assert current["schema_version"] == 2 and current["suite"] == "classification"
    with pytest.raises(ValueError, match="match the selected suite"):
        validate_config("extraction", current)


def test_incident_exercise_is_explicitly_synthetic_and_catches_critical_failures():
    config = validate_config("rag", json.loads(Path("examples/incidents/rag-profile.json").read_text(encoding="utf-8")))
    options = {k: config[k] for k in ("cases", "settings", "threshold")}
    before = run_eval("rag", "baseline", gates={"critical_tags": ["critical"]}, **options)
    after = run_eval("rag", "improved", gates={"critical_tags": ["critical"]}, **options)
    assert not before["passed_gate"] and after["passed_gate"]
    assert all(r["id"].startswith("fictional-") for r in before["results"])


def test_reports_persist_reopen_compare_and_escape_html(tmp_path):
    cases = load_cases("classification")[:1]
    cases[0]["input"] = '<script>alert("x")</script>'
    report = run_eval("classification", cases=cases, runner=lambda _: "Hardware")
    store = ReportStore(tmp_path)
    key = store.save(report, imported=True)
    assert store.load(key)["report"] == report
    assert store.list()[0]["imported"]
    output = html_report(report)
    assert '<script>' not in output and "&lt;script&gt;" in output
    assert "default-src 'none'" in output
    with pytest.raises(ValueError):
        store.load("../../outside")
    report["score"] = .3
    with pytest.raises(ValueError, match="totals"):
        validate_report(report)


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(schema_version=1),
    lambda r: r.update(results=[]),
    lambda r: r["results"][0].update(passed="yes"),
    lambda r: r["results"][0].update(checks=[]),
    lambda r: r.update(trials=2),
])
def test_invalid_reports_are_rejected(mutation):
    report = run_eval("classification", cases=load_cases("classification")[:1])
    mutation(report)
    with pytest.raises(ValueError):
        validate_report(report)
